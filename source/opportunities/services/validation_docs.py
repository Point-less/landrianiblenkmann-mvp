from django.core.exceptions import ValidationError

from opportunities.models import Validation, ValidationDocument
from utils.services import BaseService


class CreateValidationDocumentService(BaseService):
    def run(self, *, validation: Validation, name: str, document, uploaded_by=None) -> ValidationDocument:
        if not document:
            raise ValidationError({"document": "Please attach a document."})
        return ValidationDocument.objects.create(
            validation=validation,
            name=name,
            document=document,
            uploaded_by=uploaded_by,
        )


class ReviewValidationDocumentService(BaseService):
    def run(self, *, document: ValidationDocument, action: str, reviewer, comment: str | None = None) -> ValidationDocument:
        if action not in {"accept", "reject"}:
            raise ValidationError({"action": "Invalid review action."})
        if reviewer is None:
            raise ValidationError({"reviewer": "Reviewer is required."})

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
