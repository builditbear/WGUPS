# WGUPS Delivery Optimization Apparatus V1 - by Brandon Chavez, C950
# Output: Total mileage travelled by all trucks for this particular delivery solution.
# Future Fix Log:
# 1. Ensure that hash table is being utilized efficiently.
# 2. Write simple interface to check package status at given time.
# 3. Add load logic to accommodate packages with special notes.
import csv
import datetime
import sys

start_time = datetime.time(hour=8)
start_time_date = datetime.datetime.combine(datetime.date.today(), start_time)


class Package:
    def __init__(self, id, address, city, state, zipcode, delivery_deadline, masskg, special_notes):
        self.id = int(id)  # Int type more convenient as we will perform calculations with this value.
        self.address = address
        self.delivery_deadline = delivery_deadline
        self.city = city
        self.state = state
        self.zipcode = zipcode
        self.masskg = masskg
        self.special_notes = special_notes
        #  Valid entries are, "Undefined", "Delayed", "At Depot", "In Transit", and "Delivered"
        self.delivery_time: datetime.datetime = None
        self.load_time: datetime.datetime = None
        self.destination: Location = None

    def status(self, local_time: datetime.datetime):
        # If delivery/load times are unpopulated, or the current_time precedes the load_time, must be at hub.
        if (not (self.delivery_time or self.load_time)) or (local_time < self.load_time):
            return "Package #" + str(self.id) + " is currently at the hub."
        elif self.delivery_time is not None and local_time >= self.delivery_time:
            return "Package #" + str(self.id) + " was delivered at " + self.delivery_time.strftime("%I:%M") + "."
        elif local_time >= self.load_time:
            return "Package #" + str(self.id) + " is en route as of " + self.load_time.strftime("%I:%M") + "."

    # Link this package to its location in our graph via object pointer.
    def associate_destination(self, graph):
        for location in graph:
            if (self.address, self.zipcode) == (location.addr, location.zipcode):
                self.destination = location
                return
        print("No match for package address found in graph for package ID " + str(self.id) + ".")


class PackageDB:
    def __init__(self, number_of_packages):  # O(1)
        self.db_size = number_of_packages * 2
        self.db = [None] * self.db_size
        # load factor = number of elements / db_size
        self.load_factor: float = 0

    def __hashfunk(self, id):
        return (id - 1) % self.db_size

    # Generates subset of db containing all packages for use in delivery truck.
    # Allows us to keep track of what packages have been delivered without altering
    # db structure itself.
    def generate_manifest(self):
        return filter(lambda pkg: True if pkg is not None else False, self.db)

    def status_report(self, local_time: datetime.datetime):
        for pkg in self.db:
            if pkg is not None:
                print(pkg.status(local_time))

    # After load factor exceeds .5 for the first time, it should be between 1/4 and 1/2 at any given time.
    def __maintain_load_factor(self):
        self.load_factor = sum(i is not None for i in self.db) / self.db_size
        if self.load_factor > .5:
            self.db.append([None] * self.db_size)  # Expands table by factor of two to accommodate new packages.
            self.db_size = self.db_size * 2
            for i in range(len(self.db)):
                if self.db[i] is not None:
                    pkg = self.db.pop(i)  # Remove the package before replacing it at new hash index.
                    self.insert(pkg)

    # Takes a list with ordered values listed in Package init method, or a Package object.
    # Assumes that there is always an empty spot/tombstone in db: Db will resize itself to maintain optimal load factor.
    def insert(self, package_details):
        if type(package_details) is list:
            pkg = Package(*package_details)
        elif type(package_details) is Package:
            pkg = package_details
        else:
            print("Invalid type for insertion into package database.")
            return
        # Iteratively look at the next slot until an open slot or tombstone is found.
        for i in range(self.db_size):
            key = self.__hashfunk(pkg.id + i)
            if self.db[i] is None or self.db[i] == "tombstone":
                self.db[i] = pkg
                self.__maintain_load_factor()
                return
        print("Error: The entire hash table was searched, but no empty slot was found.")
        print("Please inspect load factor expansion logic.")

    def search(self, id):
        # Iteratively look at buckets until desired pkg or empty slot is found.
        # If everything is hashed uniquely, O(1) runtime.
        for i in range(self.db_size):
            key = self.__hashfunk(id + i)
            pkg = self.db[key]
            if pkg is None:
                print("Package id " + str(id) + " not found in database.")
                return
            elif pkg is not None and pkg != "tombstone" and pkg.id == id:
                return pkg
        # If execution reaches here, we've checked every possible hash key possible.
        print("Package id " + str(id) + " was not found in database.")

    def remove(self, id):
        # Similar behavior to search, but bucket's contents are replaced with a tombstone
        # when the desired package is found.
        for i in range(self.db_size):
            key = self.__hashfunk(id + i)
            pkg = self.db[key]
            if pkg is None:
                print("Package id " + str(id) + " not found in database.")
                return
            elif pkg is not None and pkg != "tombstone" and pkg.id == id:
                self.db[key] = "tombstone"
        # If execution reaches here, we've checked every possible hash key possible.
        print("Package id " + str(id) + " was not found in database.")


class Location:
    def __init__(self, id, parent_graph, name, addr, zipcode, distances):
        self.id = int(id)
        self.parent_graph = parent_graph
        self.name = name
        self.addr = addr
        self.zipcode = zipcode
        self.shortest_known_path = sys.maxsize
        self.previous_location = None
        self.distances = []
        for distance in distances:
            if distance != '':
                self.distances.append(distance)
            else:
                break

    def get_distance_to(self, location_id: int):
        # To avoid data duplication, the graph's structure mirrors that of the WGUPS Distance Table file:
        # Each location stores only distance values for previous entries in the graph, exploiting the bidirectional
        # nature of the data, and the fact that the distance table represents a full mesh graph.
        if location_id == self.id:
            return 0
        # If the destination is a previous entry in the graph, the distance can be found in local "edge" list.
        if location_id < self.id:
            return self.distances[location_id]
        # If the destination is a later entry in the graph, the distance can be found in that location's list.
        elif location_id > self.id:
            return self.parent_graph[location_id].distances[self.id]

    def reset_path(self):
        self.shortest_known_path = sys.maxsize
        self.previous_location = None


class Truck:
    def __init__(self, db, location: Location, avg_speed=18, capacity=16, mileage=0):
        self.avg_speed = avg_speed
        self.capacity = capacity
        # In this scenario, WGUPS is so wealthy that their trucks are brand new - 0 mileage!
        self.mileage = mileage
        self.db: PackageDB = db
        self.delivery_list = []
        self.location: Location = location

    # Calculates time of day for a given truck based on how far it has travelled at that point in time.
    def __current_time(self) -> datetime.datetime:
        time_since_day_start = datetime.timedelta(hours=self.mileage / self.avg_speed)
        return start_time_date + time_since_day_start

    # Need to update this once Dijkstra is working with logic for handling special notes & deadlines.
    # Optional arg "load_cap" can be used to load only up to a certain number of packages at once
    # (provided there are packages available to load and that the truck itself is not already full).
    def load(self, manifest, load_cap=sys.maxsize):
        # Provided we have not exceeded capacity, and manifest isn't empty,
        # remove the next pkg from manifest, update it's load time, and "load" onto truck.
        counter = 0
        while (len(self.delivery_list) < self.capacity) and manifest and counter < load_cap:
            current_pkg = manifest.pop(0)
            current_pkg.load_time = self.__current_time()
            self.delivery_list.append(current_pkg)
            counter += 1

    def deliver(self, pkg):
        self.delivery_list.remove(pkg)
        pkg.delivery_time = self.__current_time()


def csv_to_manifest(csv_name):
    manifest = []
    with open(csv_name, newline='') as manifest_csv:
        reader = csv.DictReader(manifest_csv)
        for package in reader:
            manifest.append(Package(package["Package ID"], package["Address"], package["City"],
                                    package["State"], package["Zip"], package["Delivery Deadline"],
                                    package["MassKG"], package["Special Notes"]))
    return manifest


# The first 3 columns in the csv, in order, should be name, addr, zip, followed by
# Entries for distances to other hubs.
def csv_to_graph(csv_name):
    graph = []
    with open(csv_name, newline='') as distance_table:
        reader = csv.reader(distance_table)
        index = 0
        for entry in reader:
            distances = []
            for dist in entry[3:]:
                if not dist:
                    break
                else:
                    distances.append(float(dist))
            graph.append(Location(index, graph, entry[0], entry[1], entry[2], distances))
            index += 1
    return graph


# Traces path of given location back to the origin location, and stores path (in order of first to last location
# visited) in the empty list passed in.
def trace_path(loc: Location, path: list):
    path.append(loc)
    # Now, if there is a previous location, it should be asked to add itself to the path (recursive step)
    if loc.previous_location:
        trace_path(loc.previous_location, path)
    # If there isn't, we have reached the origin, and we should reverse the list so it reads
    # from startpoint to endpoint.
    else:
        path.reverse()


def print_path(loc: Location):
    path = []
    trace_path(loc, path)
    for i in range(len(path)):
        if i == (len(path) - 1):
            print(path[i].name)
        else:
            print(path[i].name + " --> ", end='')


# Based on insertion sort algorithm.
def sort_by_dist_ascending(locations, origin: Location):
    for i in range(1, len(locations)):
        for j in range(i, 0, -1):
            if locations[j-1].get_distance_to(origin.id) > locations[j].get_distance_to(origin.id):
                # Swap indices of locations.
                temp = locations[j-1]
                locations[j-1] = locations[j]
                locations[j] = temp


def dijkstra_sp(g: list, start_loc_id, dest_id):
    # start has 0 dist from itself, and will be the first location to be visited.
    g[start_loc_id].shortest_known_path = 0
    unvisited = []
    # Extract all locations from graph and enqueue to be visited, then sort by proximity to start location.
    for loc in g:
        loc.reset_path()
        unvisited.append(loc)
    sort_by_dist_ascending(unvisited, g[start_loc_id])
    while unvisited:
        # Visit closest destination until we have reached the destination specified by dest_id.
        current_loc = unvisited.pop(0)
        if current_loc.id == dest_id:
            break
        for loc in unvisited:
            distance = current_loc.get_distance_to(loc.id)
            alt_path = current_loc.shortest_known_path + distance
            if alt_path < loc.shortest_known_path:
                loc.shortest_known_path = alt_path
                loc.previous_location = current_loc
    print("The shortest known path to " + g[dest_id].name + " from " + g[start_loc_id].name + " is "
          + str(g[dest_id].shortest_known_path) + " miles.")
    print_path(g[dest_id])


def deliver_packages(t: Truck, g: list):
    destinations = []
    # Determine locations we must visit, and shortest path to each from truck's current location.
    for pkg in t.delivery_list:
        if pkg.destination not in destinations:
            destinations.append(pkg.destination)
    for destination in destinations:
        dijkstra_sp(g, t.location.id, destination.id)
    destinations.sort(key=lambda d: d.shortest_known_path)
    while destinations:
        # Travel to the nearest location, update our location and mileage incurred by trip, deliver packages.
        t.location = destinations.pop(0)
        t.mileage += t.location.shortest_known_path
        for pkg in t.delivery_list:
            if pkg.destination is t.location:
                t.deliver(pkg)
        for destination in destinations:
            dijkstra_sp(g, t.location.id, destination.id)
        destinations.sort(key=lambda d: d.shortest_known_path)


if __name__ == '__main__':
    # Translate raw package and location details into data structures we can operate on.
    graph = csv_to_graph("WGUPS Distance Table.csv")
    manifest = csv_to_manifest("WGUPS Package File.csv")
    # PackageDB is a hash table for packages with some handy class methods and fields.
    db = PackageDB(len(manifest))
    # Populate the db, while linking each package to it's destination for easy access.
    for package in manifest:
        db.insert(package)
        package.associate_destination(graph)
    t1 = Truck(db, graph[0])
    t2 = Truck(db, graph[0])
    t1.load(manifest)
    t2.load(manifest)
    deliver_packages(t1, graph)
