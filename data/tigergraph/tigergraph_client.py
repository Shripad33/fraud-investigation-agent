import os
import pyTigerGraph


# ============================================================
# TIGERGRAPH CONFIGURATION
# ============================================================

TG_HOST = os.getenv("TG_HOST", "https://YOUR-TIGERGRAPH-HOST")
TG_GRAPH = "fraud_detection"
TG_TOKEN = os.getenv("TG_TOKEN")


def get_connection():
    """
    Create and return a TigerGraph connection.
    """

    if not TG_TOKEN:
        raise RuntimeError(
            "TG_TOKEN is not set. Set it as an environment variable."
        )

    if "YOUR-TIGERGRAPH-HOST" in TG_HOST:
        raise RuntimeError(
            "TG_HOST is not configured. Set the TigerGraph host."
        )

    return pyTigerGraph.TigerGraphConnection(
        host=TG_HOST,
        graphname=TG_GRAPH,
        apiToken=TG_TOKEN,
    )


def test_connection():
    """
    Test the TigerGraph connection.
    """

    try:
        conn = get_connection()

        print("Connected to TigerGraph")
        print("Graph:", TG_GRAPH)

        result = conn.gsql(
            "INTERPRET QUERY () FOR GRAPH fraud_detection "
            "{ PRINT Customer.*; }"
        )

        print(result)
        return True

    except Exception as e:
        print("TigerGraph connection failed:")
        print(e)
        return False


if __name__ == "__main__":
    test_connection()