"""Контроллер формы обратной связи."""

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.middleware.rate_limit import rate_limit_guard
from app.schemas.common import ErrorResponse
from app.schemas.contact import AIAnalysisPublic, ContactRequestIn, ContactResponse
from app.services.contact_service import ContactService

router = APIRouter(prefix="/api", tags=["Contact"])


@router.post(
    "/contact",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_guard)],
    summary="Отправить обращение из формы обратной связи",
    description=(
        "Принимает данные формы, валидирует их, прогоняет сообщение через AI "
        "(тональность / категория / приоритет + черновик ответа), сохраняет "
        "обращение в БД и отправляет два письма (владельцу и пользователю)."
    ),
    responses={
        422: {"model": ErrorResponse, "description": "Ошибка валидации"},
        429: {"model": ErrorResponse, "description": "Превышен лимит запросов"},
    },
)
async def submit_contact(
    payload: ContactRequestIn,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> ContactResponse:
    request_id = request.state.request_id
    service = ContactService(session)

    # AI-анализ + сохранение — синхронно (результат нужен в ответе).
    analysis = await service.process(
        payload,
        ip_address=request.state.client_ip,
        request_id=request_id,
    )

    # Письма — в фоне: ответ клиенту не ждёт SMTP.
    background_tasks.add_task(service.send_notifications, payload, analysis, request_id)

    return ContactResponse(
        request_id=request_id,
        message="Спасибо! Мы получили ваше обращение и скоро свяжемся с вами.",
        analysis=AIAnalysisPublic(
            sentiment=analysis.sentiment,
            category=analysis.category,
            priority=analysis.priority,
            provider=analysis.provider,
        ),
    )
