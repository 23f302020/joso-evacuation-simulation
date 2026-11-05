"""Isolated native repair candidate, never applied to the selected bundle."""


def remap_source(raw):
    newline = b'\r\n' if b'\r\n' in raw else b'\n'
    start = b'    const ConstMSEdgeVector& edges = newRoute->getEdges();'
    old = b'''        if (std::find(myRoute->begin(), myRoute->end(), stopEdge) == myRoute->end()) {
            it = myPastStops.erase(it);
        } else {
            ++it;
        }'''.replace(b'\n', newline)
    new = b'''        // A routeID replacement may omit the already-traveled prefix.
        // Keep a past stop only at the corresponding already-traveled position.
        const int remappedIndex = it->routeIndex
            + (int)(myCurrEdge - myRoute->begin()) - previousCurrentIndex;
        if (remappedIndex < 0 || remappedIndex > (int)(myCurrEdge - myRoute->begin())
                || myRoute->getEdges()[remappedIndex] != stopEdge) {
            it = myPastStops.erase(it);
        } else {
            it->routeIndex = remappedIndex;
            ++it;
        }'''.replace(b'\n', newline)
    if raw.count(start) != 1 or raw.count(old) != 1 or b'previousCurrentIndex' in raw:
        raise ValueError('Exact unmodified route-replacement anchors required')
    return raw.replace(start, b'    const int previousCurrentIndex = (int)(myCurrEdge - myRoute->begin());' + newline + start).replace(old, new)
