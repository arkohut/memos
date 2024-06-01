from sqlalchemy.orm import Session
from .schemas import Library, NewLibraryParam, Folder
from .models import LibraryModel, FolderModel


def get_library_by_id(library_id: int, db: Session) -> Library | None:
    return db.query(Library).filter(Library.id == library_id).first()


def create_library(library: NewLibraryParam, db: Session) -> Library:
    db_library = LibraryModel(name=library.name)
    db.add(db_library)
    db.commit()
    db.refresh(db_library)

    for folder_path in library.folders:
        db_folder = FolderModel(path=str(folder_path), library_id=db_library.id)
        db.add(db_folder)

    db.commit()
    return Library(
        id=db_library.id,
        name=db_library.name,
        folders=[Folder(id=db_folder.id, name=db_folder.path) for db_folder in db_library.folders],
        plugins=[]
    )
