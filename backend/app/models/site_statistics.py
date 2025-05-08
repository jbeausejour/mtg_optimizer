from datetime import datetime, timezone
from sqlalchemy import Column, Integer, ForeignKey, Float, DateTime
from sqlalchemy.orm import relationship
from app import Base


class SiteStatistics(Base):
    __tablename__ = "site_statistics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    site_id = Column(Integer, ForeignKey("site.id"), nullable=False)
    scan_id = Column(Integer, ForeignKey("scan.id"), nullable=False)

    found_cards = Column(Integer, nullable=False, default=0)
    total_cards = Column(Integer, nullable=False, default=0)
    total_variants = Column(Integer, nullable=False, default=0)

    search_time = Column(Float, nullable=True)
    extract_time = Column(Float, nullable=True)
    total_time = Column(Float, nullable=True)

    site = relationship("Site", backref="site_statistics")
    scan = relationship("Scan", backref="site_statistics")

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "site_id": self.site_id,
            "scan_id": self.scan_id,
            "found_cards": self.found_cards,
            "total_cards": self.total_cards,
            "total_variants": self.total_variants,
            "search_time": self.search_time,
            "extract_time": self.extract_time,
            "total_time": self.total_time,
        }


# Statistic bucket structure to collect site results summary:
class SiteScrapeStats:
    def __init__(self):
        self.site_stats = {}

    def record_site(
        self, site_id, site_name, search_time, extract_time, total_time, found_cards, total_cards, total_variants
    ):
        self.site_stats[site_id] = {
            "site_name": site_name,
            "search_time": search_time,
            "extract_time": extract_time,
            "total_time": total_time,
            "found_cards": found_cards,
            "total_cards": total_cards,
            "total_variants": total_variants,
        }

    @classmethod
    def from_db(cls, stats_list):
        instance = cls()
        for stat in stats_list:
            instance.site_stats[stat.site.id] = {
                "site_name": stat.site.name,
                "search_time": stat.search_time,
                "extract_time": stat.extract_time,
                "total_time": stat.total_time,
                "found_cards": stat.found_cards,
                "total_cards": stat.total_cards,
                "total_variants": stat.total_variants,
            }
        return instance

    async def persist_to_db(self, session, scan_id):
        from app.models.site_statistics import SiteStatistics

        for site_id, stats in self.site_stats.items():
            entry = SiteStatistics(
                site_id=site_id,  # ✅ This is now truly an integer ID
                scan_id=scan_id,
                found_cards=stats["found_cards"],
                total_cards=stats["total_cards"],
                total_variants=stats["total_variants"],
                search_time=stats["search_time"],
                extract_time=stats["extract_time"],
                total_time=stats["total_time"],
            )
            session.add(entry)
            await session.flush()

    def log_summary(self, logger):
        logger.info("=" * 95)
        logger.info(
            f"{'Site':<25} {'# Found':<8} {'Total Cards':<12} {'Variants':<9} {'Search(s)':<10} {'Extract(s)':<11} {'Total(s)':<9}"
        )
        logger.info("-" * 95)

        for site_id, stats in sorted(self.site_stats.items(), key=lambda item: item[1]["found_cards"], reverse=True):
            try:
                site_name = stats.get("site_name", "Unknown")
                found_cards = stats.get("found_cards", 0)
                total_cards = stats.get("total_cards", 0)
                total_variants = stats.get("total_variants", 0)
                search_time = stats.get("search_time", 0.0)
                extract_time = stats.get("extract_time", 0.0)
                total_time = stats.get("total_time", 0.0)

                logger.info(
                    f"{site_name:<25} {found_cards:<8} {total_cards:<12} {total_variants:<9} "
                    f"{search_time:<10.2f} {extract_time:<11.2f} {total_time:<9.2f}"
                )
            except KeyError as e:
                logger.error(f"Missing key {e} in site stats for site_id {site_id}")

        logger.info("=" * 95 + "\n")
