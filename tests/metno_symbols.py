"""Every symbol code MET Norway can return (https://api.met.no/weatherapi/weathericon/2.0/documentation)."""
WITHOUT_TIME = [
    "cloudy", "fog",
    "heavyrain", "heavyrainandthunder", "heavysleet", "heavysleetandthunder", "heavysnow", "heavysnowandthunder",
    "lightrain", "lightrainandthunder", "lightsleet", "lightsleetandthunder", "lightsnow", "lightsnowandthunder",
    "rain", "rainandthunder", "sleet", "sleetandthunder", "snow", "snowandthunder",
]
WITH_TIME = [
    "clearsky", "fair", "partlycloudy",
    "heavyrainshowers", "heavyrainshowersandthunder", "heavysleetshowers", "heavysleetshowersandthunder",
    "heavysnowshowers", "heavysnowshowersandthunder",
    "lightrainshowers", "lightrainshowersandthunder", "lightsleetshowers", "lightssleetshowersandthunder",
    "lightsnowshowers", "lightssnowshowersandthunder",
    "rainshowers", "rainshowersandthunder", "sleetshowers", "sleetshowersandthunder",
    "snowshowers", "snowshowersandthunder",
]
ALL = WITHOUT_TIME + [f"{base}_{time}" for base in WITH_TIME for time in ("day", "night", "polartwilight")]
