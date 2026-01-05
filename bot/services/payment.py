"""YooKassa payment service for handling payments."""

import logging
import uuid
from typing import Optional, Dict, Any

from yookassa import Configuration, Payment
from yookassa.domain.response import PaymentResponse

from bot.config import config
from bot.keyboards.inline import SHOP_PACKAGES

logger = logging.getLogger(__name__)


# Initialize YooKassa configuration
def init_yookassa():
    """Initialize YooKassa SDK with credentials."""
    if config.yookassa_shop_id and config.yookassa_secret_key:
        Configuration.account_id = config.yookassa_shop_id
        Configuration.secret_key = config.yookassa_secret_key
        logger.info("YooKassa SDK initialized")
    else:
        logger.warning("YooKassa credentials not configured")


class PaymentService:
    """Service for creating and managing YooKassa payments."""
    
    @staticmethod
    def is_configured() -> bool:
        """Check if YooKassa is properly configured."""
        return bool(config.yookassa_shop_id and config.yookassa_secret_key)
    
    @staticmethod
    def create_payment(
        user_id: int,
        telegram_id: int,
        package_key: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new payment in YooKassa.
        
        Args:
            user_id: Internal user ID
            telegram_id: Telegram user ID
            package_key: Package key (starter, small, medium, pro, vip)
        
        Returns:
            Dict with payment_id, confirmation_url, amount, tokens
            or None if failed
        """
        if not PaymentService.is_configured():
            logger.error("YooKassa not configured")
            return None
        
        if package_key not in SHOP_PACKAGES:
            logger.error(f"Unknown package: {package_key}")
            return None
        
        package = SHOP_PACKAGES[package_key]
        amount = package["price"]
        tokens = package["tokens"]
        
        # Generate idempotence key
        idempotence_key = str(uuid.uuid4())
        
        try:
            # Create payment
            payment = Payment.create({
                "amount": {
                    "value": f"{amount}.00",
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": config.yookassa_return_url or f"https://t.me/{config.bot_token.split(':')[0]}"
                },
                "capture": True,  # Auto-capture payment
                "description": f"Пакет {package['name']} ({tokens} токенов)",
                "metadata": {
                    "user_id": user_id,
                    "telegram_id": telegram_id,
                    "package": package_key,
                    "tokens": tokens,
                }
            }, idempotence_key)
            
            logger.info(f"Created payment {payment.id} for user {telegram_id}, package {package_key}")
            
            return {
                "payment_id": payment.id,
                "confirmation_url": payment.confirmation.confirmation_url,
                "amount": f"{amount}.00",
                "tokens": tokens,
                "package": package_key,
                "status": payment.status,
            }
            
        except Exception as e:
            logger.error(f"Failed to create payment: {e}")
            return None
    
    @staticmethod
    def create_gift_payment(
        user_id: int,
        telegram_id: int,
        package_key: str,
        gift_id: int,
        recipient_username: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new gift payment in YooKassa.
        
        Args:
            user_id: Internal user ID (sender)
            telegram_id: Telegram user ID (sender)
            package_key: Package key (starter, small, medium, pro, vip)
            gift_id: Gift record ID
            recipient_username: Recipient's username
        
        Returns:
            Dict with payment_id, confirmation_url, amount, tokens
            or None if failed
        """
        if not PaymentService.is_configured():
            logger.error("YooKassa not configured")
            return None
        
        if package_key not in SHOP_PACKAGES:
            logger.error(f"Unknown package: {package_key}")
            return None
        
        package = SHOP_PACKAGES[package_key]
        amount = package["price"]
        tokens = package["tokens"]
        
        # Generate idempotence key
        idempotence_key = str(uuid.uuid4())
        
        try:
            # Create payment
            payment = Payment.create({
                "amount": {
                    "value": f"{amount}.00",
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": config.yookassa_return_url or f"https://t.me/{config.bot_token.split(':')[0]}"
                },
                "capture": True,
                "description": f"Подарок для @{recipient_username} | Аксель AI",
                "metadata": {
                    "user_id": user_id,
                    "telegram_id": telegram_id,
                    "package": package_key,
                    "tokens": tokens,
                    "is_gift": True,
                    "gift_id": gift_id,
                    "recipient_username": recipient_username,
                }
            }, idempotence_key)
            
            logger.info(f"Created gift payment {payment.id} for user {telegram_id}, gift to @{recipient_username}")
            
            return {
                "payment_id": payment.id,
                "confirmation_url": payment.confirmation.confirmation_url,
                "amount": f"{amount}.00",
                "tokens": tokens,
                "package": package_key,
                "status": payment.status,
            }
            
        except Exception as e:
            logger.error(f"Failed to create gift payment: {e}")
            return None
    
    @staticmethod
    def get_payment(payment_id: str) -> Optional[PaymentResponse]:
        """
        Get payment status from YooKassa.
        
        Args:
            payment_id: YooKassa payment ID
        
        Returns:
            PaymentResponse or None if failed
        """
        if not PaymentService.is_configured():
            return None
        
        try:
            payment = Payment.find_one(payment_id)
            return payment
        except Exception as e:
            logger.error(f"Failed to get payment {payment_id}: {e}")
            return None
    
    @staticmethod
    def parse_webhook_notification(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse webhook notification from YooKassa.
        
        Args:
            data: Raw webhook data
        
        Returns:
            Parsed payment data or None if invalid
        """
        try:
            event = data.get("event")
            obj = data.get("object", {})
            
            if not event or not obj:
                logger.warning("Invalid webhook data: missing event or object")
                return None
            
            payment_id = obj.get("id")
            status = obj.get("status")
            paid = obj.get("paid", False)
            metadata = obj.get("metadata", {})
            
            return {
                "event": event,
                "payment_id": payment_id,
                "status": status,
                "paid": paid,
                "user_id": metadata.get("user_id"),
                "telegram_id": metadata.get("telegram_id"),
                "package": metadata.get("package"),
                "tokens": metadata.get("tokens"),
                "amount": obj.get("amount", {}).get("value"),
            }
            
        except Exception as e:
            logger.error(f"Failed to parse webhook: {e}")
            return None


# Initialize on module load
init_yookassa()
