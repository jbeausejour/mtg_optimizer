class Card:
    def __init__(self, Site="", Name="", Edition="", Version="", Foil=False, Quality="", Language="", Quantity=None, Price=None):
        self.Site = Site
        self.Name = Name
        self.Edition = Edition
        self.Version = Version
        self.Foil = Foil
        self.Quality = Quality
        self.Language = Language
        self.Quantity = Quantity
        self.Price = Price

    def to_dict(self):
        return {
            'Site': self.Site,
            'Name': self.Name,
            'Edition': self.Edition,
            'Version': self.Version,
            'Foil': self.Foil,
            'Quality': self.Quality,
            'Language': self.Language,
            'Quantity': self.Quantity,
            'Price': self.Price
        }

    def __eq__(self, other):
        if not isinstance(other, Card):
            return False
        return (
            (self.Site, self.Name, self.Edition, self.Version, self.Foil, self.Quality, self.Language, self.Quantity, self.Price) ==
            (other.Site, other.Name, other.Edition, other.Version, other.Foil, other.Quality, other.Language, other.Quantity, other.Price)
        )

    def __hash__(self):
        return hash((self.Site, self.Name, self.Edition, self.Version, self.Foil, self.Quality, self.Language, self.Quantity, self.Price))
