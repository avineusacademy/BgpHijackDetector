from datetime import datetime
import pybgpstream

def test_bgpstream_ribs():
    # Fixed past time interval (UTC)
    from_time = "2023-01-01T00:00:00Z"
    until_time = "2023-01-01T00:10:00Z"

    print(f"Testing BGPStream RIB snapshot from {from_time} until {until_time}")

    stream = pybgpstream.BGPStream(
        from_time=from_time,
        until_time=until_time,
        record_type="ribs"
    )

    count = 0
    try:
        for elem in stream:
            print(f"Prefix: {elem.prefix}, Origin AS: {elem.origin_as}, Time: {datetime.utcfromtimestamp(elem.time)}")
            count += 1
            if count >= 10:
                break
    except Exception as e:
        print(f"Error fetching BGP ribs: {e}")

    if count == 0:
        print("No ribs received. Check the time interval or connection.")
    else:
        print(f"Received {count} rib records successfully.")

if __name__ == "__main__":
    test_bgpstream_ribs()
