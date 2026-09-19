from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from finsight import config
from finsight.auth.security import create_access_token, decode_access_token
from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.models import User
from finsight.zerodha import state as link_state
from finsight.zerodha.client import exchange_request_token, get_oauth_login_url
from finsight.zerodha.schemas import HoldingItem, PortfolioSummary, ZerodhaLinkBody, ZerodhaLoginUrl
from finsight.zerodha.service import (
    get_holdings,
    save_zerodha_token,
    sync_holdings_for_user,
)

router = APIRouter()

CONNECT_TOKEN_MINUTES = 5


def _cookie_secure() -> bool:
    return config.ZERODHA_REDIRECT_URI.lower().startswith("https://")


def _start_link(user_id: int) -> RedirectResponse:
    """Set the signed state cookie and send the browser to Kite's login page."""
    cookie_value, nonce = link_state.issue(user_id)
    url = get_oauth_login_url(state=nonce)
    if not url:
        raise HTTPException(status_code=503, detail="Zerodha API not configured")
    redirect = RedirectResponse(url=url, status_code=302)
    redirect.set_cookie(
        link_state.COOKIE,
        cookie_value,
        max_age=link_state.MAX_AGE,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/zerodha/",
    )
    return redirect


@router.get("/login-url", response_model=ZerodhaLoginUrl)
def login_url():
    url = get_oauth_login_url()
    if not url:
        raise HTTPException(status_code=503, detail="Zerodha API not configured")
    return ZerodhaLoginUrl(login_url=url)


@router.get("/connect-url")
def connect_url(current_user: User = Depends(get_current_user)):
    """
    URL the frontend opens in a new tab to start linking. It carries a
    5-minute token that is only good for /connect-redirect — not an API
    credential — because a navigation cannot send the Bearer header.
    """
    if not config.ZERODHA_REDIRECT_URI:
        raise HTTPException(status_code=503, detail="ZERODHA_REDIRECT_URI not configured")
    base_url = config.ZERODHA_REDIRECT_URI.rsplit("/zerodha/", 1)[0]
    token = create_access_token(
        data={"sub": str(current_user.id), "purpose": "zerodha_connect"},
        expires_minutes=CONNECT_TOKEN_MINUTES,
    )
    return {"connect_url": f"{base_url}/zerodha/connect-redirect?token={token}"}


@router.get("/connect")
def connect_zerodha(current_user: User = Depends(get_current_user)):
    """Start Zerodha OAuth for the authenticated user (API clients)."""
    return _start_link(current_user.id)


@router.get("/connect-redirect")
def connect_redirect(token: str):
    """Browser entry point: validates the short-lived connect token, then starts OAuth."""
    payload = decode_access_token(token)
    if not payload or payload.get("purpose") != "zerodha_connect" or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired connect token")
    return _start_link(int(payload["sub"]))


@router.get("/callback", response_class=HTMLResponse)
def zerodha_callback(
    request: Request,
    request_token: str | None = None,
    status: str | None = None,
    state: str | None = None,
    session: Session = Depends(get_session),
):
    """
    Kite redirects here with ?request_token=…&status=success&state=<nonce>.
    The link is accepted only if the signed cookie from /connect verifies and
    its nonce matches `state`.
    """
    if not request_token or status != "success":
        return HTMLResponse("<h1>Zerodha callback</h1><p>Missing request_token or status.</p>", status_code=400)

    user_id = link_state.verify(request.cookies.get(link_state.COOKIE), state)
    if user_id is None:
        return HTMLResponse(
            "<h1>Link not accepted</h1><p>This login was not started from FinSight, or it expired. "
            "Go back to the app and click Connect again.</p>",
            status_code=400,
        )

    data = exchange_request_token(request_token)
    if not data or not data.get("access_token"):
        return HTMLResponse(
            "<h1>Token exchange failed</h1><p>Invalid request_token or API config.</p>", status_code=400
        )

    save_zerodha_token(session, user_id, data["access_token"])
    response = HTMLResponse("<h1>Zerodha linked</h1><p>You can close this window and use the app.</p>")
    response.delete_cookie(link_state.COOKIE, path="/zerodha/")
    return response


@router.post("/link")
def link_zerodha(
    body: ZerodhaLinkBody,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Exchange a request_token obtained out-of-band and store it for the current user."""
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
