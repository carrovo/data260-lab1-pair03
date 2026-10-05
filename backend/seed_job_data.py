from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models import Company, Job
from backend.app.security import hash_password


COMPANIES = [
    {
        "email": "seed.talentbridge.p03@example.com",
        "name": "TalentBridge Labs",
        "city": "San Jose",
    },
    {
        "email": "seed.greenwave.p03@example.com",
        "name": "GreenWave Analytics",
        "city": "Santa Clara",
    },
    {
        "email": "seed.fremontrobotics.p03@example.com",
        "name": "Fremont Robotics",
        "city": "Fremont",
    },
]


JOBS = [
    {
        "company_email": "seed.talentbridge.p03@example.com",
        "title": "Data Analyst Intern",
        "description": (
            "Analyze business data, create dashboards, "
            "and communicate findings to stakeholders."
        ),
        "city": "San Jose",
    },
    {
        "company_email": "seed.talentbridge.p03@example.com",
        "title": "Backend Engineering Intern",
        "description": (
            "Build Python APIs and support database-backed "
            "web services."
        ),
        "city": "San Jose",
    },
    {
        "company_email": "seed.greenwave.p03@example.com",
        "title": "Product Analyst",
        "description": (
            "Study product usage data and help prioritize "
            "new product features."
        ),
        "city": "Santa Clara",
    },
    {
        "company_email": "seed.greenwave.p03@example.com",
        "title": "Machine Learning Intern",
        "description": (
            "Prepare datasets and evaluate machine learning "
            "models for forecasting."
        ),
        "city": "Santa Clara",
    },
    {
        "company_email": "seed.fremontrobotics.p03@example.com",
        "title": "Data Engineer",
        "description": (
            "Develop data pipelines and maintain reliable "
            "analytics infrastructure."
        ),
        "city": "Fremont",
    },
    {
        "company_email": "seed.fremontrobotics.p03@example.com",
        "title": "Robotics Software Intern",
        "description": (
            "Support robotics software development, testing, "
            "and sensor-data processing."
        ),
        "city": "Fremont",
    },
]


def seed_job_data() -> None:
    db = SessionLocal()
    created_companies = 0
    created_jobs = 0

    try:
        companies_by_email = {}

        for company_data in COMPANIES:
            company = db.scalar(
                select(Company).where(
                    Company.email == company_data["email"]
                )
            )

            if company is None:
                company = Company(
                    email=company_data["email"],
                    password_hash=hash_password("SeedPassword123"),
                    name=company_data["name"],
                    city=company_data["city"],
                )
                db.add(company)
                db.flush()
                created_companies += 1

            companies_by_email[company.email] = company

        for job_data in JOBS:
            company = companies_by_email[
                job_data["company_email"]
            ]

            existing_job = db.scalar(
                select(Job).where(
                    Job.company_id == company.id,
                    Job.title == job_data["title"],
                    Job.city == job_data["city"],
                )
            )

            if existing_job is None:
                db.add(
                    Job(
                        company_id=company.id,
                        title=job_data["title"],
                        description=job_data["description"],
                        city=job_data["city"],
                    )
                )
                created_jobs += 1

        db.commit()

        print(f"Created companies: {created_companies}")
        print(f"Created jobs: {created_jobs}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_job_data()