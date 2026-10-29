
import json
from accounts.permissions import get_authorized_staff_profile
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from procedures.models import Procedure

from .rag import answer_with_rag, safety_response

@require_POST
def chatbot_api(request):
    """Answer authenticated staff questions for a selected procedure."""
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Authentication required"},
            status=401,
        )

    if get_authorized_staff_profile(request.user) is None:
        return JsonResponse(
            {"error": "You are not authorized to use the preparation assistant."},
            status=403,
        )

    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    if not isinstance(data, dict):
        return JsonResponse(
            {"error": "JSON body must be an object"},
            status=400,
        )

    question = data.get("question", "")
    procedure_id = data.get("procedure_id")

    if not isinstance(question, str):
        return JsonResponse({"error": "Question must be text"}, status=400)

    question = question.strip()
    if not question:
        return JsonResponse({"error": "Question is required"}, status=400)

    if len(question) > 1000:
        return JsonResponse(
            {"error": "Question must be 1000 characters or fewer"},
            status=400,
        )

    if isinstance(procedure_id, bool) or not (
        isinstance(procedure_id, int)
        or (isinstance(procedure_id, str) and procedure_id.isdigit())
    ):
        return JsonResponse(
            {"error": "A valid procedure_id is required"},
            status=400,
        )

    procedure = (
        Procedure.objects
        .select_related("protocol")
        .filter(pk=procedure_id)
        .first()
    )

    if procedure is None:
        return JsonResponse({"error": "Procedure not found"}, status=404)

    escalation = safety_response(question)
    if escalation is not None:
        return JsonResponse(escalation)

    return JsonResponse(
        answer_with_rag(question, protocol_id=procedure.protocol_id)
    )

def answer_question(question, protocol_id=None):
    """Return a safe, source-grounded preparation answer."""
    escalation = safety_response(question)
    if escalation is not None:
        return escalation

    return answer_with_rag(question, protocol_id=protocol_id)
