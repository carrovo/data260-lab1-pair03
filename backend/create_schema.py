from backend.app import models
from backend.app.database import Base, engine


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print("Database schema created successfully.")


if __name__ == "__main__":
    main()