
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .rag import answer_with_rag, safety_response


def answer_question(question):
    """Return a safe, source-grounded preparation answer."""
    escalation = safety_response(question)

    if escalation is not None:
        return escalation

    return answer_with_rag(question)


@csrf_exempt
def chatbot_api(request):
    """Handle chatbot questions through a JSON POST endpoint."""
    if request.method != "POST":
        return JsonResponse(
            {"error": "POST request required"},
            status=405,
        )

    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "Invalid JSON body"},
            status=400,
        )

    if not isinstance(data, dict):
        return JsonResponse(
            {"error": "JSON body must be an object"},
            status=400,
        )

    question = data.get("question", "")

    if not isinstance(question, str):
        return JsonResponse(
            {"error": "Question must be text"},
            status=400,
        )

    question = question.strip()

    if not question:
        return JsonResponse(
            {"error": "Question is required"},
            status=400,
        )

    if len(question) > 1000:
        return JsonResponse(
            {"error": "Question must be 1000 characters or fewer"},
            status=400,
        )

    result = answer_question(question)
    return JsonResponse(result)
