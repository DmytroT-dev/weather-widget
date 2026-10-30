"""Human-readable values for the widget."""


def format_temperature(celsius: float) -> str:
    rounded = round(celsius)
    if rounded == 0:  # also catches -0.3 -> "-0", which Python's "+.0f" format would print
        return "0°C"
    return f"{rounded:+d}°C"


def format_wind(speed_ms: float) -> str:
    return f"{round(speed_ms)} m/s"
