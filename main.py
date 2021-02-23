# WGUPS Delivery Optimization Apparatus V1 - by Brandon Chavez, C950
# Future Fix Log:
import csv
import datetime
import sys


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
        self.delivery_time: datetime.time = None
        self.load_time: datetime.time = None
        self.destination: Location = None

    def delivery_status(self, local_time: datetime.time):
        if (self.delivery_time is None) and (self.load_time is None):
            return "Package #" + str(self.id) + " is currently at the hub."
        elif local_time >= self.delivery_time:
            return "Package #" + str(self.id) + " was delivered at " + self.delivery_time + "."
        elif local_time >= self.load_time:
            return "Package #" + str(self.id) + " is en route as of " + self.load_time

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

    def status_report(self, local_time: datetime.time):
        for pkg in self.db:
            if pkg is not None:
                print(pkg.delivery_status(local_time))

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


class Truck:
    def __init__(self, avg_speed=18, capacity=16):
        self.avg_speed = avg_speed
        self.capacity = capacity
        self.packing_list = []

    # Need to update this once Dijstra is working with logic for handling special notes & deadlines.
    def load(self, load_time, manifest):
        for pkg in manifest:
            # Provided we have not exceeded capacity, and manifest isn't empty,
            # remove the next pkg from manifest, update it's load time, and "load" onto truck.
            if len(self.packing_list) < self.capacity and manifest:
                current_pkg = manifest.pop(pkg)
                current_pkg.update_load_time(load_time)
                self.packing_list.append(current_pkg)


class Location:
    def __init__(self, id, parent_graph, name, addr, zipcode, distances):
        self.id = id
        self.parent_graph = parent_graph
        self.name = name
        self.addr = addr
        self.zipcode = zipcode
        self.distance_from_hub = sys.maxsize
        self.previous_location = None
        self.distances = []
        for distance in distances:
            if distance != '':
                self.distances.append(distance)
            else:
                break

    def get_distance(self, origin):
        # To avoid data duplication, the graph's structure mirrors that of the WGUPS Distance Table file:
        # Each location stores only distance values for previous entries in the graph, exploiting the bidirectional
        # nature of the data, and the fact that the distance table represents a full mesh graph.
        if origin == self.id:
            return 0
        # If the destination is a previous entry in the graph, the distance can be found in local "edge" list.
        if origin < self.id:
            return self.distances[origin]
        # If the destination is a later entry in the graph, the distance can be found in that location's list.
        elif origin > self.id:
            return self.parent_graph[origin].distances[self.id]


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
            graph.append(Location(index, graph, entry[0], entry[1], entry[2], entry[3:]))
            index += 1
    return graph


def dijkstra_delivery(truck, graph):
    hub = graph[0]  # The starting vertex.
    unvisited = []
    for pkg in truck.packing_list:
        unvisited.append(pkg.destination)
    # Distance in this context is relative to the hub.
    hub.distance = 0
    # Sort unvisited destinations by their proximity to the hub.
    print(unvisited)
    sort_by_dist_ascending(unvisited, hub)
    print(unvisited)
    # while unvisited is not []:


def sort_by_dist_ascending(locations, origin):
    for i in range(1, len(locations)):
        for j in range(i, 0, -1):
            if locations[j-1].get_distance(origin) > locations[j].get_distance(origin):
                # Swap indices of locations.
                temp = locations[j-1]
                locations[j-1] = locations[j]
                locations[j] = temp


if __name__ == '__main__':
    # Translate raw package and hub details into navigable data structures we can operate on.
    graph = csv_to_graph("WGUPS Distance Table.csv")
    manifest = csv_to_manifest("WGUPS Package File.csv")

    db = PackageDB(len(manifest))
    for package in manifest:
        db.insert(package)
        package.associate_destination(graph)
    db.status_report(datetime.time(3))
    t1 = Truck()