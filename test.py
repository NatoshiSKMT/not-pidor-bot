#!/usr/bin/env python
from datetime import datetime
ts = datetime.utcfromtimestamp(1585191485)

print((datetime.today()-ts).total_seconds())
exit()
