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
        self.delivery_time = None
        self.load_time = None
        self.destination = None

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

    def get_size(self):
        return self.db_size

    def status_report(self, local_time: datetime.time):
        for package in self.db:
            if package is not None:
                print(package.delivery_status(local_time))

    def __expand_and_rehash(self):
        self.db.append([None] * self.db_size)  # Expands table by factor of two to accommodate new packages.
        self.db_size = self.db_size * 2
        for package_index in range(len(self.db)):
            if self.db[package_index] is not None:
                package = self.db.pop(package_index)  # Remove the package before replacing it at new hash index.
                self.insert(package)

    # Takes a list with ordered values listed in Package init method, or a Package object.
    def insert(self, package_details):
        if type(package_details) is list:
            package = Package(*package_details)
        elif type(package_details) is Package:
            package = package_details
        else:
            print("Invalid type for insertion into package database.")
            return

        index = (package.id - 1) % self.db_size
        if self.db[index] is None:
            self.db[index] = package
        else:
            starting_point = index
            index = (index + 1) % self.db_size  # Iteratively look at the next slot until an open slot it found.
            while index != starting_point:
                if self.db[index] is None:
                    self.db[index] = package
                    return
                index = (index + 1) % self.db_size
            self.__expand_and_rehash()  # If an empty spot isn't available we can expand the db before trying again!
            self.insert(package)

    def search(self, id):
        for package in self.db:
            if (package is not None) and (package.id == id):
                return package

    def remove(self, id):
        for package in self.db:
            if package is not None:
                if package.id == id:
                    self.db.remove(package)
                    return
        else:
            print("The given package ID is not in this database.")
            return


class Truck:
    def __init__(self, avg_speed=18, capacity=16):
        self.avg_speed = avg_speed
        self.capacity = capacity
        self.packing_list = []

    def load(self, load_time, delivery_list: list, package_db: PackageDB):
        for id in delivery_list:
            if len(self.packing_list) < self.capacity and delivery_list:
                pkg = package_db.search(delivery_list.pop(id))
                pkg.update_load_time(load_time)
                self.packing_list.append(pkg)


class Location:
    def __init__(self, name, addr, zipcode, distances):
        self.name = name
        self.addr = addr
        self.zipcode = zipcode
        self.distance_from_hub = sys.maxsize
        self.distances = []
        for distance in distances:
            if distance != '':
                self.distances.append(distance)
            else:
                break


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
        for entry in reader:
            graph.append(Location(entry[0], entry[1], entry[2], entry[3:]))
    return graph


# def dijkstra_delivery(truck, graph):
#     hub = graph[0]  # The starting vertex.
#     for location in graph:
#         location


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    # Translate raw package and hub details into navigable data structures we can operate on.
    graph = csv_to_graph("WGUPS Distance Table.csv")
    manifest = csv_to_manifest("WGUPS Package File.csv")

    db = PackageDB(len(manifest))
    for package in manifest:
        db.insert(package)
        package.associate_destination(graph)
    db.status_report(datetime.time(3))
