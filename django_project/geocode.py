import googlemaps
from environs import Env

env = Env()
env.read_env()


def geocode(address, postcode, country="UK"):
    if not address and not postcode:
        raise ValueError("Either address or postcode must be provided.")

    components = [address, country, postcode]
    query = ", ".join([comp for comp in components if comp])

    try:
        maps = googlemaps.Client(key=env.str("GOOGLE_MAPS_API_KEY"))
        result = maps.geocode(query)[0]

        if not result:
            print(f"No geocoding results found for query: {query}")
            return None

        place_id = result.get("place_id", None)
        formatted_address = result.get("formatted_address", None)
        lat = result.get("geometry", {}).get("location", {}).get("lat", None)
        lng = result.get("geometry", {}).get("location", {}).get("lng", None)

        if lat is None or lng is None or not place_id:
            raise ValueError("Incomplete geocoding result from Google Maps API")

        return formatted_address, lat, lng, place_id
    except googlemaps.exceptions.ApiError as api_error:
        print(f"Google Maps API Error: {api_error}")
    except googlemaps.exceptions.TransportError as transport_error:
        print(f"Google Maps Transport Error: {transport_error}")
    except Exception as e:
        print(f"An error occurred during geocoding: {e}")
    return None
