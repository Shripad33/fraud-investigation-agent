import pyTigerGraph


# ============================================================
# TIGERGRAPH CONFIGURATION
# ============================================================

TG_HOST = "https://YOUR-TIGERGRAPH-HOST"
TG_GRAPH = "fraud_detection"
TG_TOKEN = "YOUR-TIGERGRAPH-TOKEN"


def get_connection():
    """
    Create and return a TigerGraph connection.
    """

    conn = pyTigerGraph.TigerGraphConnection(
        host=TG_HOST,
        graphname=TG_GRAPH,
        apiToken=TG_TOKEN,
    )

    return conn


def test_connection():
    """
    Test the TigerGraph connection.
    """

    conn = get_connection()

    print("Connected to TigerGraph")
    print("Graph:", TG_GRAPH)

    try:
        result = conn.gsql("INTERPRET QUERY () FOR GRAPH fraud_detection { PRINT Customer.*; }")
        print(result)
        return True

    except Exception as e:
        print("TigerGraph query failed:")
        print(e)
        return False


if __name__ == "__main__":
    test_connection()