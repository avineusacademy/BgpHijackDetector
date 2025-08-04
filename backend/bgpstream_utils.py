from datetime import datetime
import pybgpstream

def get_bgpstream_data(from_time: str, until_time: str):
    stream = pybgpstream.BGPStream(
        from_time=from_time,
        until_time=until_time,
        record_type="updates"
    )
    updates = []
    for elem in stream:
        if elem.type == "A":
            updates.append({
                "prefix": elem.prefix,
                "origin_as": int(elem.origin_as),
                "timestamp": datetime.utcfromtimestamp(elem.time).isoformat()
            })
        if len(updates) >= 1000:
            break
    return updates
