from pathlib import Path

from django.core.exceptions import ValidationError

from opportunities.models import Validation, ValidationDocument
from utils.services import BaseService


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".pdf", ".png"}


class CreateValidationDocumentService(BaseService):
    def run(
        self,
        *,
        validation: Validation,
        document_type: str,
        document,
        uploaded_by=None,
        name: str | None = None,
    ) -> ValidationDocument:
        if not document:
            raise ValidationError({"document": "Please attach a document."})
        if document_type not in ValidationDocument.DocumentType.values:
            raise ValidationError({"document_type": "Invalid document type."})
        suffix = Path(document.name or "").suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            allowed_display = ", ".join(ext.upper().lstrip(".") for ext in sorted(ALLOWED_EXTENSIONS))
            raise ValidationError({"document": f"Formato inválido. Usa archivos {allowed_display}."})

        label_map = dict(ValidationDocument.DocumentType.choices)
        return ValidationDocument.objects.create(
            validation=validation,
            document_type=document_type,
            name=name or label_map.get(document_type, document_type.title()),
            document=document,
            uploaded_by=uploaded_by,
        )


class ReviewValidationDocumentService(BaseService):
    def run(self, *, document: ValidationDocument, action: str, reviewer, comment: str | None = None) -> ValidationDocument:
        if action not in {"accept", "reject"}:
            raise ValidationError({"action": "Invalid review action."})
        if reviewer is None:
            raise ValidationError({"reviewer": "Reviewer is required."})
        if document.validation.state != Validation.State.PRESENTED:
            raise ValidationError({"document": "Documents can only be reviewed once the validation is presented."})

        if action == "accept":
            document.accept(reviewer=reviewer, comment=comment)
        else:
            document.reject(reviewer=reviewer, comment=comment)
        document.save(update_fields=["status", "reviewer_comment", "decided_by", "decided_at", "updated_at"])
        return document


__all__ = [
    "CreateValidationDocumentService",
    "ReviewValidationDocumentService",
]
