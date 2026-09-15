class LayananTidakTersedia(RuntimeError):
    def __init__(self, layanan: str, sebab: str) -> None:
        self.layanan = layanan
        self.sebab = sebab
        super().__init__(f"{layanan} tidak tersedia: {sebab}")
