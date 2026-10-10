from enum import StrEnum


class ApplicationStatus(StrEnum):
    PENDING = "Pending"
    REVIEWED = "Reviewed"
    DECLINED = "Declined"
