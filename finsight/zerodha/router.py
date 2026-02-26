from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, HTMLResponse

from sqlmodel import Session

from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.models import User
from finsight.zerodha.schemas import ZerodhaLoginUrl, ZerodhaLinkBody, HoldingItem, PortfolioSummary
from finsight.zerodha.service import (
    get_oauth_login_url,
    get_holdings,
    get_zerodha_token_for_user,
    save_zerodha_token,
    sync_holdings_for_user,
)
from finsight.zerodha.client import exchange_request_token

router = APIRouter()

# Cookie used to associate Zerodha redirect with the user who started the flow
ZERODHA_LINK_COOKIE = "zerodha_link_uid"
ZERODHA_LINK_MAX_AGE = 600  # 10 minutes


@router.get("/login-url", response_model=ZerodhaLoginUrl)
def login_url():
    url = get_oauth_login_url()
    if not url:
        raise HTTPException(status_code=503, detail="Zerodha API not configured")
    return ZerodhaLoginUrl(login_url=url)


@router.get("/connect-url")
def connect_url(current_user: User = Depends(get_current_user)):
    """
    Return the full connect-redirect URL using the ngrok base URL.
    The frontend should open this URL in a new tab.
    """
    from finsight.config import ZERODHA_REDIRECT_URI
    from finsight.auth.security import create_access_token

    if not ZERODHA_REDIRECT_URI:
        raise HTTPException(status_code=503, detail="ZERODHA_REDIRECT_URI not configured")

    # Derive the ngrok base URL from the redirect URI
    # e.g. https://xxx.ngrok-free.dev/zerodha/callback → https://xxx.ngrok-free.dev
    base_url = ZERODHA_REDIRECT_URI.rsplit("/zerodha/", 1)[0]

    token = create_access_token(data={"sub": str(current_user.id)})
    full_url = f"{base_url}/zerodha/connect-redirect?token={token}"
    return {"connect_url": full_url}


@router.get("/connect")
def connect_zerodha(
    response: Response,
    current_user: User = Depends(get_current_user),
):
    """
    Start Zerodha OAuth: set cookie with user id and redirect to Zerodha login.
    After login Zerodha redirects to your Redirect URL; our callback exchanges the token and stores it.
    """
    url = get_oauth_login_url()
    if not url:
        raise HTTPException(status_code=503, detail="Zerodha API not configured")
    redirect = RedirectResponse(url=url, status_code=302)
    redirect.set_cookie(
        ZERODHA_LINK_COOKIE,
        str(current_user.id),
        max_age=ZERODHA_LINK_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return redirect


@router.get("/connect-redirect")
def connect_redirect(
    token: str,
    session: Session = Depends(get_session),
):
    """
    Frontend-friendly: pass JWT as ?token= query param.
    Sets cookie with user id, then redirects to Zerodha login.
    The callback will read the cookie and auto-link the access token.
    """
    from finsight.auth.security import decode_access_token

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    url = get_oauth_login_url()
    if not url:
        raise HTTPException(status_code=503, detail="Zerodha API not configured")

    redirect = RedirectResponse(url=url, status_code=302)
    redirect.set_cookie(
        ZERODHA_LINK_COOKIE,
        str(payload["sub"]),
        max_age=ZERODHA_LINK_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return redirect


@router.get("/callback", response_class=HTMLResponse)
def zerodha_callback(
    request: Request,
    request_token: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
):
    """
    Zerodha redirects here after login with ?request_token=...&status=success.
    If we have a cookie (user started from /zerodha/connect), we exchange the token and store it.
    Otherwise we show the request_token so you can POST it to /zerodha/link with your Bearer token.
    """
    if not request_token or status != "success":
        return HTMLResponse(
            content="<h1>Zerodha callback</h1><p>Missing request_token or status.</p>",
            status_code=400,
        )
    user_id_str = request.cookies.get(ZERODHA_LINK_COOKIE)
    response = HTMLResponse()
    # Clear cookie in any case
    response.delete_cookie(ZERODHA_LINK_COOKIE, path="/")

    data = exchange_request_token(request_token)
    if not data or not data.get("access_token"):
        return HTMLResponse(
            content="<h1>Token exchange failed</h1><p>Invalid request_token or API config.</p>",
            status_code=400,
        )
    access_token = data["access_token"]

    if user_id_str:
        try:
            user_id = int(user_id_str)
            save_zerodha_token(session, user_id, access_token)
            return HTMLResponse(
                content="<h1>Zerodha linked</h1><p>You can close this window and use the app.</p>"
            )
        except ValueError:
            pass

    # No cookie: show token for manual link
    html = f"""
    <h1>Zerodha login successful</h1>
    <p>To link this session to your FinSight account, call:</p>
    <pre>POST /zerodha/link\nContent-Type: application/json\nAuthorization: Bearer YOUR_JWT\n\n{{ "request_token": "{request_token}" }}</pre>
    <p>Or use the same flow again after clicking "Connect Zerodha" in the app (so the cookie is set).</p>
    """
    return HTMLResponse(content=html)


@router.post("/link")
def link_zerodha(
    body: ZerodhaLinkBody,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Exchange a request_token (from Zerodha redirect) and store access_token for the current user.
    """
    request_token = (body.request_token or "").strip()
    if not request_token:
        raise HTTPException(status_code=400, detail="request_token required")
    data = exchange_request_token(request_token)
    if not data or not data.get("access_token"):
        raise HTTPException(status_code=400, detail="Invalid request_token or API config")
    save_zerodha_token(session, current_user.id, data["access_token"])
    return {"status": "linked"}


@router.post("/sync")
def sync_holdings(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Fetch holdings from Zerodha and save to your portfolio."""
    holdings_list = sync_holdings_for_user(session, current_user.id)
    if holdings_list is None:
        raise HTTPException(
            status_code=400,
            detail="Zerodha not linked. Use /zerodha/connect or POST /zerodha/link with request_token.",
        )
    return {"synced": len(holdings_list)}


@router.get("/holdings", response_model=PortfolioSummary)
def holdings(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Return holdings from DB (sync from Zerodha first via POST /zerodha/sync if needed)."""
    holdings_list = get_holdings(session, current_user.id)
    items = [
        HoldingItem(
            symbol=h.symbol,
            quantity=h.quantity,
            avg_price=h.avg_price,
            current_price=h.current_price,
        )
        for h in holdings_list
    ]
    total = sum((h.current_price or h.avg_price) * h.quantity for h in holdings_list)
    return PortfolioSummary(holdings=items, total_value=total)
