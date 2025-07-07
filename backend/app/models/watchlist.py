from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Column, Integer, String, DateTime, Numeric, ForeignKey, Text
from sqlalchemy.orm import relationship, validates

from app import Base


class Watchlist(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    card_name = Column(String, nullable=False)
    set_code = Column(String, nullable=True)
    mtgstocks_id = Column(Integer, nullable=True)
    mtgstocks_url = Column(String, nullable=True)
    target_price = Column(Numeric(10, 2), nullable=True)
    # Removed is_active - we use true deletion now
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user = relationship("User", backref="watchlist_items")
    price_alerts = relationship("PriceAlert", backref="watchlist_item", cascade="all, delete-orphan")
    scan_status = relationship("WatchlistScanStatus", backref="watchlist_item", cascade="all, delete-orphan")

    def to_dict(self, include_latest_alert=True):
        """
        Convert to dictionary, optionally including latest alert data

        Args:
            include_latest_alert: If True, will try to include latest alert data
                                Only set to True if price_alerts relationship is eager-loaded
        """
        base_dict = {
            "id": self.id,
            "user_id": self.user_id,
            "card_name": self.card_name,
            "set_code": self.set_code,
            "mtgstocks_id": self.mtgstocks_id,
            "mtgstocks_url": self.mtgstocks_url,
            "target_price": float(self.target_price) if self.target_price else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        # Only access price_alerts if explicitly requested and if it's safe to do so
        if include_latest_alert:
            try:
                # Check if the relationship is loaded to avoid lazy loading issues
                if hasattr(self, "_sa_instance_state") and "price_alerts" in self._sa_instance_state.loaded_attrs:
                    if self.price_alerts:
                        latest_alert = max(self.price_alerts, key=lambda x: x.created_at)
                        base_dict.update(
                            {
                                "current_market_price": (
                                    float(latest_alert.market_price) if latest_alert.market_price else None
                                ),
                                "best_price": float(latest_alert.current_price) if latest_alert.current_price else None,
                                "best_price_site": latest_alert.site_name if latest_alert else None,
                                "last_checked": latest_alert.created_at.isoformat() if latest_alert else None,
                            }
                        )
                    else:
                        base_dict.update(
                            {
                                "current_market_price": None,
                                "best_price": None,
                                "best_price_site": None,
                                "last_checked": None,
                            }
                        )
                else:
                    # Relationship not loaded, set defaults
                    base_dict.update(
                        {
                            "current_market_price": None,
                            "best_price": None,
                            "best_price_site": None,
                            "last_checked": None,
                        }
                    )
            except Exception:
                # If anything goes wrong, just set defaults
                base_dict.update(
                    {
                        "current_market_price": None,
                        "best_price": None,
                        "best_price_site": None,
                        "last_checked": None,
                    }
                )
        else:
            # Default values when not including alert data
            base_dict.update(
                {
                    "current_market_price": None,
                    "best_price": None,
                    "best_price_site": None,
                    "last_checked": None,
                }
            )

        return base_dict

    @validates("card_name")
    def validate_card_name(self, key, card_name):
        if not card_name or not card_name.strip():
            raise ValueError("Card name is required")
        return card_name.strip()

    @validates("target_price")
    def validate_target_price(self, key, target_price):
        if target_price is not None:
            if isinstance(target_price, str):
                target_price = Decimal(target_price)
            if target_price < 0:
                raise ValueError("Target price cannot be negative")
        return target_price

    @validates("user_id")
    def validate_user_id(self, key, user_id):
        if not user_id:
            raise ValueError("User ID is required")
        return user_id


class PriceAlert(Base):
    __tablename__ = "price_alert"

    id = Column(Integer, primary_key=True)
    watchlist_id = Column(Integer, ForeignKey("watchlist.id"), nullable=False)
    site_name = Column(String, nullable=False)
    current_price = Column(Numeric(10, 2), nullable=False)
    market_price = Column(Numeric(10, 2), nullable=True)  # From MTGStocks
    price_difference = Column(Numeric(10, 2), nullable=True)  # market_price - current_price
    percentage_difference = Column(Numeric(5, 2), nullable=True)  # Percentage below market
    alert_type = Column(String, default="price_drop")  # price_drop, target_reached, good_deal
    is_viewed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Additional metadata
    scan_result_id = Column(
        Integer, ForeignKey("scan_result.id"), nullable=True
    )  # Link to the scan result that triggered this
    notes = Column(Text, nullable=True)

    # Relationships
    scan_result = relationship("ScanResult", backref="price_alerts")

    def to_dict(self):
        return {
            "id": self.id,
            "watchlist_id": self.watchlist_id,
            "card_name": self.watchlist_item.card_name if self.watchlist_item else None,
            "site_name": self.site_name,
            "current_price": float(self.current_price),
            "market_price": float(self.market_price) if self.market_price else None,
            "price_difference": float(self.price_difference) if self.price_difference else None,
            "percentage_difference": float(self.percentage_difference) if self.percentage_difference else None,
            "alert_type": self.alert_type,
            "is_viewed": self.is_viewed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "scan_result_id": self.scan_result_id,
            "notes": self.notes,
        }

    @validates("current_price", "market_price", "price_difference")
    def validate_prices(self, key, price):
        if price is not None:
            if isinstance(price, str):
                price = Decimal(price)
            if price < 0:
                raise ValueError(f"{key} cannot be negative")
        return price

    @validates("percentage_difference")
    def validate_percentage(self, key, percentage):
        if percentage is not None:
            if isinstance(percentage, str):
                percentage = Decimal(percentage)
            if percentage < -100 or percentage > 100:
                raise ValueError("Percentage difference must be between -100 and 100")
        return percentage

    @validates("watchlist_id")
    def validate_watchlist_id(self, key, watchlist_id):
        if not watchlist_id:
            raise ValueError("Watchlist ID is required")
        return watchlist_id

    @validates("site_name")
    def validate_site_name(self, key, site_name):
        if not site_name or not site_name.strip():
            raise ValueError("Site name is required")
        return site_name.strip()

    @validates("alert_type")
    def validate_alert_type(self, key, alert_type):
        valid_types = ["price_drop", "target_reached", "good_deal", "manual"]
        if alert_type not in valid_types:
            raise ValueError(f"Alert type must be one of: {', '.join(valid_types)}")
        return alert_type


class WatchlistScanStatus(Base):
    """Track when we last checked prices for watchlist items"""

    __tablename__ = "watchlist_scan_status"

    id = Column(Integer, primary_key=True)
    watchlist_id = Column(Integer, ForeignKey("watchlist.id"), nullable=False)
    last_scanned = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    scan_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    consecutive_errors = Column(Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "watchlist_id": self.watchlist_id,
            "last_scanned": self.last_scanned.isoformat() if self.last_scanned else None,
            "scan_count": self.scan_count,
            "last_error": self.last_error,
            "consecutive_errors": self.consecutive_errors,
        }
