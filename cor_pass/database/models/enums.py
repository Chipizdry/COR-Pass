"""
Database Enums
All enum types used across database models
"""
import enum


# User & Auth Enums
class Status(enum.Enum):
    """User account status"""
    premium: str = "premium"
    basic: str = "basic"


class AuthSessionStatus(enum.Enum):
    """COR-ID auth session status"""
    PENDING: str = "pending"
    APPROVED: str = "approved"
    REJECTED: str = "rejected"
    TIMEOUT: str = "timeout"


# Doctor & Medical Professional Enums
class Doctor_Status(enum.Enum):
    """Doctor registration and approval status"""
    pending: str = "pending"
    approved: str = "approved"
    agreed: str = "agreed"
    rejected: str = "rejected"
    need_revision: str = "need_revision"


# Patient Enums
class PatientStatus(enum.Enum):
    """Patient status in medical workflow"""
    registered = "registered"
    diagnosed = "diagnosed"
    under_treatment = "under_treatment"
    hospitalized = "hospitalized"
    discharged = "discharged"
    died = "died"
    in_process = "in_process"
    referred_for_additional_consultation = "referred_for_additional_consultation"


class PatientClinicStatus(enum.Enum):
    """Patient clinic status with additional lab states"""
    registered = "registered"
    diagnosed = "diagnosed"
    under_treatment = "under_treatment"
    hospitalized = "hospitalized"
    discharged = "discharged"
    died = "died"
    in_process = "in_process"
    referred_for_additional_consultation = "referred_for_additional_consultation"
    awaiting_report = "awaiting_report"
    completed = "completed"
    error = "error"


# Laboratory Enums
class MacroArchive(enum.Enum):
    """Типы макроархива для параметров кейса"""
    ESS = "ESS - без залишку"
    RSS = "RSS - залишок"


class DecalcificationType(enum.Enum):
    """Типы декальцинации для параметров кейса"""
    ABSENT = "Відсутня"
    EDTA = "EDTA"
    ACIDIC = "Кислотна"


class SampleType(enum.Enum):
    """Типы образцов для параметров кейса"""
    NATIVE = "Нативний біоматеріал"
    BLOCKS = "Блоки/Скельця"


class MaterialType(enum.Enum):
    """Типы материалов (исследований) для параметров кейса"""
    R = "Resectio"
    B = "Biopsy"
    E = "Excisio"
    C = "Cytology"
    CB = "Cellblock"
    S = "Second Opinion"
    A = "Autopsy"
    EM = "Electron Microscopy"
    OTHER = "Інше"


class UrgencyType(enum.Enum):
    """Типы срочности для параметров кейса"""
    S = "Standard"
    U = "Urgent"
    F = "Frozen"


class FixationType(enum.Enum):
    """Типы фиксации для параметров кейса"""
    NBF_10 = "10% NBF"
    OSMIUM = "Osmium"
    BOUIN = "Bouin"
    ALCOHOL = "Alcohol"
    GLUTARALDEHYDE_2 = "2% Glutaraldehyde"
    OTHER = "Інше"


class StudyType(enum.Enum):
    """Типы исследований для направления"""
    CYTOLOGY = "Цитологія"
    HISTOPATHOLOGY = "Патогістологія"
    IMMUNOHISTOCHEMISTRY = "Імуногістохімія"
    FISH_CISH = "FISH/CISH"
    CB = "Cellblock"
    S = "Second Opinion"
    A = "Autopsy"
    EM = "Electron Microscopy"
    OTHER = "Інше"


class StainingType(enum.Enum):
    """Типы окрашивания для стёкол"""
    HE = "H&E"
    ALCIAN_PAS = "Alcian PAS"
    CONGO_RED = "Congo red"
    MASSON_TRICHROME = "Masson Trichrome"
    VAN_GIESON = "van Gieson"
    ZIEHL_NEELSEN = "Ziehl Neelsen"
    WARTHIN_STARRY_SILVER = "Warthin-Starry Silver"
    GROCOTT_METHENAMINE_SILVER = "Grocott's Methenamine Silver"
    TOLUIDINE_BLUE = "Toluidine Blue"
    PERLS_PRUSSIAN_BLUE = "Perls Prussian Blue"
    PAMS = "PAMS"
    PICROSIRIUS = "Picrosirius"
    SIRIUS_RED = "Sirius red"
    THIOFLAVIN_T = "Thioflavin T"
    TRICHROME_AFOG = "Trichrome AFOG"
    VON_KOSSA = "von Kossa"
    GIEMSA = "Giemsa"
    OTHAR = "Othar"

    def abbr(self) -> str:
        """Возвращает сокращение для печати"""
        overrides = {
            "H&E": "H&E",
            "PAMS": "PAM",
            "Othar": "O",
        }
        if self.value in overrides:
            return overrides[self.value]

        parts = self.value.replace("-", " ").replace("'", "").split()
        abbr = "".join(word[0].upper() for word in parts)

        return abbr[:3]


class Grossing_status(enum.Enum):
    """Статус обработки материала в лаборатории"""
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    CREATED = "CREATED"
    IN_SIGNING_STATUS = "IN_SIGNING_STATUS"


# Medicine Enums
class MedicineIntakeStatus(enum.Enum):
    """Статус приема лекарств"""
    PLANNED = "planned"  # Запланированный прием
    COMPLETED = "completed"  # Прием выполнен
    SKIPPED = "skipped"  # Пропущен
    DELAYED = "delayed"  # Отложен


# Device Enums
class DeviceStatus(enum.Enum):
    """Status of manufactured devices"""
    MANUFACTURED = "manufactured"
    ACTIVATED = "activated"
    BLOCKED = "blocked"


class AccessLevel(enum.Enum):
    """Access level for device sharing"""
    READ = "read"
    READ_WRITE = "read_write"
    SHARE = "share"


# Medical Card Enums
class MedicalCardAccessLevel(enum.Enum):
    """Уровни доступа к медкарте"""
    VIEW = "view"  # Может смотреть
    EDIT = "edit"  # Может редактировать (и смотреть)
    SHARE = "share"  # Может распространять (редактировать, смотреть и делиться с другими)


class MedicalCardPurpose(enum.Enum):
    """Цель предоставления доступа к медкарте"""
    RELATIVE = "relative"  # Для родственника
    DOCTOR = "doctor"  # Для врача
    OTHER = "other"  # Другое
