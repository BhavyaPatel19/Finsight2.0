from sqlmodel import Field, SQLModel


class DocumentSection(SQLModel, table=True):
    __tablename__ = "document_sections"

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    title: str
    level: int = 1  # 1=chapter, 2=section, 3=subsection
    parent_id: int | None = Field(default=None, foreign_key="document_sections.id")
    start_page: int
    end_page: int | None = None
