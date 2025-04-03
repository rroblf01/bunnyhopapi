import cProfile
import pstats
from bunnyhopapi.server import Server
from bunnyhopapi.models import Endpoint


class HealthEndpoint(Endpoint):
    path = "/health"

    def get(self, headers):
        return 200, {"message": "GET /health"}


def run_server():
    server = Server(host="0.0.0.0", port=8000)
    server.include_endpoint_class(HealthEndpoint)
    server.run()


if __name__ == "__main__":
    profiler = cProfile.Profile()
    profiler.enable()

    try:
        run_server()
    except KeyboardInterrupt:
        pass
    finally:
        profiler.disable()

        stats = pstats.Stats(profiler)
        stats.sort_stats(pstats.SortKey.CUMULATIVE)
        stats.dump_stats("server_profile.prof")
