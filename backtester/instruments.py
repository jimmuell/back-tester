from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    symbol: str
    point_value: float
    tick_size: float

    @property
    def tick_value(self) -> float:
        return self.point_value * self.tick_size


MES = Instrument("MES", 5.0, 0.25)   # tick_value = 1.25
ES = Instrument("ES", 50.0, 0.25)    # tick_value = 12.50
