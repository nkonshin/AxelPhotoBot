"""Payment handlers for YooKassa integration."""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.config import config
from bot.keyboards.inline import (
    CallbackData,
    SHOP_PACKAGES,
    back_keyboard,
    main_menu_keyboard,
)
from bot.services.payment import PaymentService
from bot.db.database import get_session_maker
from bot.db.repositories import UserRepository, PaymentRepository

logger = logging.getLogger(__name__)

router = Router(name="payment")


def payment_keyboard(confirmation_url: str):
    """Create keyboard with payment link."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="💳 Оплатить",
            url=confirmation_url,
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔄 Проверить оплату",
            callback_data="payment:check",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад в магазин",
            callback_data=CallbackData.TOKENS,
        )
    )
    
    return builder.as_markup()


@router.callback_query(F.data.startswith("shop:"))
async def handle_shop_package(callback: CallbackQuery) -> None:
    """Handle shop package selection - create payment."""
    package_key = callback.data.replace("shop:", "")
    
    # Handle contact manager
    if package_key == "contact":
        support = config.support_username or "@support"
        await callback.message.answer(
            text=(
                "📞 <b>Связаться с менеджером</b>\n\n"
                f"Если у вас возникли проблемы с оплатой или есть вопросы, "
                f"напишите нам: {support}\n\n"
                "Мы ответим в течение 10 минут! ⚡"
            ),
            parse_mode="HTML",
        )
        await callback.answer()
        return
    
    # Check if package exists
    if package_key not in SHOP_PACKAGES:
        await callback.answer("❌ Неизвестный пакет")
        return
    
    package = SHOP_PACKAGES[package_key]
    
    # Check if YooKassa is configured
    if not PaymentService.is_configured():
        await callback.answer(
            f"💳 Оплата пакета {package['name']} ({package['price']} ₽) скоро будет доступна!",
            show_alert=True,
        )
        return
    
    # Get user
    user_tg = callback.from_user
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_tg.id)
        
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return
        
        # Create payment
        payment_data = PaymentService.create_payment(
            user_id=user.id,
            telegram_id=user_tg.id,
            package_key=package_key,
        )
        
        if not payment_data:
            await callback.answer(
                "❌ Ошибка создания платежа. Попробуйте позже.",
                show_alert=True,
            )
            return
        
        # Save payment to database
        payment_repo = PaymentRepository(session)
        await payment_repo.create(
            user_id=user.id,
            yookassa_payment_id=payment_data["payment_id"],
            package=package_key,
            tokens_amount=payment_data["tokens"],
            amount_value=payment_data["amount"],
            confirmation_url=payment_data["confirmation_url"],
            status=payment_data["status"],
        )
    
    # Show payment message
    await callback.message.edit_text(
        text=(
            f"💳 <b>Оплата пакета {package['name']}</b>\n\n"
            f"<b>Сумма:</b> {package['price']} ₽\n"
            f"<b>Токены:</b> {package['tokens']} 🪙\n\n"
            "Нажмите кнопку «Оплатить» для перехода на страницу оплаты.\n\n"
            "После оплаты нажмите «Проверить оплату» или просто вернитесь в бота — "
            "токены зачислятся автоматически! ✨"
        ),
        reply_markup=payment_keyboard(payment_data["confirmation_url"]),
    )
    await callback.answer()


@router.callback_query(F.data == "payment:check")
async def check_payment_status(callback: CallbackQuery) -> None:
    """Check payment status manually."""
    user_tg = callback.from_user
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        payment_repo = PaymentRepository(session)
        
        user = await user_repo.get_by_telegram_id(user_tg.id)
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return
        
        # Get latest pending payment
        payment = await payment_repo.get_latest_pending(user.id)
        
        if not payment:
            await callback.answer("Нет активных платежей")
            return
        
        # Check status in YooKassa
        yookassa_payment = PaymentService.get_payment(payment.yookassa_payment_id)
        
        if not yookassa_payment:
            await callback.answer("❌ Ошибка проверки статуса")
            return
        
        # Update status in DB
        old_status = payment.status
        payment.status = yookassa_payment.status
        payment.paid = yookassa_payment.paid
        
        if yookassa_payment.status == "succeeded" and yookassa_payment.paid:
            # Payment successful - add tokens
            if old_status != "succeeded":
                await user_repo.update_tokens(user.id, payment.tokens_amount)
                logger.info(
                    f"Payment {payment.yookassa_payment_id} succeeded, "
                    f"added {payment.tokens_amount} tokens to user {user_tg.id}"
                )
                
                # Notify admins
                from bot.services.admin_notify import notify_admins
                await notify_admins(
                    f"💰 <b>Новая оплата!</b>\n\n"
                    f"Пользователь: @{user.username or '—'} ({user_tg.id})\n"
                    f"Пакет: {SHOP_PACKAGES.get(payment.package, {}).get('name', payment.package)}\n"
                    f"Сумма: {payment.amount_value} ₽\n"
                    f"Токены: +{payment.tokens_amount} 🪙",
                    title="Оплата"
                )
            
            await session.commit()
            
            new_balance = user.tokens + payment.tokens_amount
            await callback.message.edit_text(
                text=(
                    "✅ <b>Оплата прошла успешно!</b>\n\n"
                    f"<b>Пакет:</b> {SHOP_PACKAGES.get(payment.package, {}).get('name', payment.package)}\n"
                    f"<b>Зачислено:</b> +{payment.tokens_amount} 🪙\n"
                    f"<b>Ваш баланс:</b> {new_balance} 🪙\n\n"
                    "Спасибо за покупку! Теперь можно творить магию 🎨"
                ),
                reply_markup=main_menu_keyboard(),
            )
            await callback.answer("✅ Оплата успешна!")
            
        elif yookassa_payment.status == "canceled":
            await session.commit()
            await callback.message.edit_text(
                text=(
                    "❌ <b>Платёж отменён</b>\n\n"
                    "Платёж был отменён или истёк срок оплаты.\n"
                    "Попробуйте создать новый платёж."
                ),
                reply_markup=back_keyboard(),
            )
            await callback.answer("Платёж отменён")
            
        elif yookassa_payment.status == "pending":
            await session.commit()
            await callback.answer(
                "⏳ Платёж ещё обрабатывается. Подождите немного и проверьте снова.",
                show_alert=True,
            )
        else:
            await session.commit()
            await callback.answer(f"Статус: {yookassa_payment.status}")
