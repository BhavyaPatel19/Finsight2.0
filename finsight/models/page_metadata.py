from sqlmodel import Field, SQLModel


class PageMetadata(SQLModel, table=True):
    __tablename__ = "page_metadata"

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    page_number: int
    section_title: str | None = None
    sub_section_title: str | None = None
    text: str = ""
