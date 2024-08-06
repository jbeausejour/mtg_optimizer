from app.models.scan import Scan, ScanResult

class ScanService:
    @staticmethod
    def get_scan_results(scan_id):
        scan = Scan.query.get_or_404(scan_id)
        return scan

    @staticmethod
    def get_all_scan_results():
        scans = Scan.query.order_by(Scan.created_at.desc()).limit(5).all()
        return scans
