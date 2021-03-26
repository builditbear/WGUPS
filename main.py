# WGUPS Optimized Delivery Projection V1.0 - by Brandon Chavez, Student ID#001118464, C950
# Devises a sub-optimal but heuristically efficient delivery route for a number of packages to a number of locations
# whose necessary info is provided via csv files. Allows for checking expected status of all packages or any particular
# package at any given time, and will also output the anticipated mileage to be incurred by end of day for all
# utilized vehicles.
import csv
import datetime
import sys
import re
from typing import Optional
from typing import List

# Note that although this program is chiefly concerned with time of day rather than the date (this program is designedd
# for "Daily Local Deliveries" after all), it uses datetime objects, since the time object type in Python's
# datetime library does not support comparisons or strptime (a method which allows us to extract a time from
# a pre-formatted string). This causes quite a bit of extra work, but it will allow for tracking deliveries spanning
# multiple days in the future if WGUPS should expand its operation.
start_time = datetime.time(hour=8)
start_time_date = datetime.datetime.combine(datetime.date.today(), start_time)


# An abstraction of all of the important characteristics of a package. Can be queried directly for info and status.
class Package:
    def __init__(self, pkg_id, address, city, state, zipcode, delivery_deadline, masskg, special_notes):  # O(1)
        self.pkg_id = int(pkg_id)  # Int type more convenient as we will perform calculations with this value.
        self.address = address
        self.delivery_deadline = delivery_deadline
        self.city = city
        self.state = state
        self.zipcode = zipcode
        self.masskg = masskg
        self.special_notes = special_notes
        # A dependency in this context is a package that this package must be loaded onto the same truck with.
        self.dependencies: List[Package] or None = []
        # This field is used for storing the time that delayed packages arrive at hub, or alternatively, the time
        # at which WGUPS "receives" the correct address for an incorrectly addressed package, thus making that package
        # available for delivery.
        self.time_available: Optional[datetime.datetime] = None
        self.delivery_time: Optional[datetime.datetime] = None
        self.load_time: Optional[datetime.datetime] = None
        self.destination: Optional[Location] = None

    # Determines where a package is located at the given time, based on the given time's relation to this package's
    # time of delivery and loading.
    def status(self, local_time: datetime.datetime):  # O(1)
        # If delivery/load times are unpopulated, or the current_time precedes the load_time, must be at hub.
        if (not (self.delivery_time or self.load_time)) or (local_time < self.load_time):
            print("Package #" + str(self.pkg_id) + " is currently at the hub.")
        # If the package posseses a delivery time, and the current_time is later than that time, package is delivered.
        elif self.delivery_time is not None and local_time >= self.delivery_time:
            print("Package #" + str(self.pkg_id) + " was delivered at " + self.delivery_time.strftime("%I:%M") + ".")
        # Otherwise, it is some time between the time this package was loaded but before it has been delivered.
        # Therefore, it must be en route to its destination.
        elif local_time >= self.load_time:
            print("Package #" + str(self.pkg_id) + " is en route as of " + self.load_time.strftime("%I:%M") + ".")

    def info(self):  # O(1)
        print("Delivery address: " + self.address + ", " + self.city + ", " + self.zipcode)
        print("Delivery deadline: " + self.delivery_deadline)
        print("Package weight: " + self.masskg + " kg")
        if self.special_notes:
            print(self.special_notes)
        if self.load_time:
            print("Loaded at: " + self.load_time.strftime("%H:%M") + ".")

    # Link this package to the location it must be delivered to in our graph via object pointer.
    def associate_destination(self, g: list):  # O(n)
        for location in g:
            if (self.address, self.zipcode) == (location.addr, location.zipcode):
                self.destination = location
                return
        print("No match for package address found in graph for package ID " + str(self.pkg_id) + ".")


# A specialized hash table for package objects which also contains basic metadata on the hash table as well as
# functions and methods for modifying and interacting with data.
class PackageDB:
    # Initializes with far more space than is expected to be necessary in order to ensure rapid lookup time.
    def __init__(self, number_of_packages):  # O(1)
        self.db_size = number_of_packages * 2
        self.db: List[Package or None] = [None] * self.db_size
        # load factor = number of elements / db_size
        self.load_factor: float = 0

    # Adjusted to reflect starting index of 0 vs first package ID being 1.
    def __hashfunc(self, pkg_id):  # O(1)
        return (pkg_id - 1) % self.db_size

    # Allows querying a package for it's info and status at the given time.
    def get_status(self, pkg_id, local_time: datetime.datetime):  # O(n)
        pkg = self.search(pkg_id)
        if pkg is not None:
            pkg.status(local_time)

    # Queries this database for a comprehensive report on the status of all packages at the given time.
    def status_report(self, local_time: datetime.datetime):  # O(n)
        for pkg in self.db:
            if pkg is not None:
                self.get_status(pkg.pkg_id, local_time)

    # Once the database has been populated, it's load factor should be 1/2. In the event that more packages need to be
    # added for delivery, this will ensure that the load factor remains between 1/4 and 1/2 at any given time.
    # In the future, this logic could be enhanced to shrink the database if the load factor is low enough, which could
    # help save memory wasted on unused "buckets".
    def __maintain_load_factor(self):  # O(n^2)
        self.load_factor = sum(i is not None for i in self.db) / self.db_size
        if self.load_factor > .5:
            self.db.append([None] * self.db_size)  # Expands table by factor of two to accommodate new packages.
            self.db_size = self.db_size * 2
            for i in range(len(self.db)):
                if self.db[i] is not None:
                    pkg = self.db.pop(i)  # Remove the package before replacing it at new hash index.
                    self.insert(pkg)  # O(n)

    # Takes a list with ordered values listed in Package init method, or a Package object.
    # Assumes that there is always an empty spot/tombstone in db: Db will resize itself to maintain optimal load factor.
    def insert(self, package_details):  # O(n)
        if type(package_details) is list:
            pkg = Package(*package_details)
        elif type(package_details) is Package:
            pkg = package_details
        else:
            print("Invalid type for insertion into package database.")
            return
        # Check for delayed packages: Query user for time of arrival.
        p2 = re.compile('Delayed on flight')
        if p2.match(pkg.special_notes):
            update_time_available(pkg, "We have detected that this package is delayed.\n"
                                       "Please enter ETA in format 'HH:MM' or 'H:MM':\n")
        # Check for incorrectly addressed packages: Query user for correct addr, and time it will be available.
        p3 = re.compile('Wrong address listed')
        if p3.match(pkg.special_notes):
            update_time_available(pkg, "We have detected that this package bears an incorrect address.\n"
                                       "Please enter ETA in format 'HH:MM' or 'H:MM':\n")
            update_pkg_addr(pkg)
        # If the slot this pkg hashes to is occupied, iteratively look at the next slot until
        # an open slot or tombstone is found. Will resize self as load factor is exceeded.
        for i in range(self.db_size):
            key = self.__hashfunc(pkg.pkg_id + i)
            if self.db[key] is None or self.db[key] == "tombstone":
                self.db[key] = pkg
                self.__maintain_load_factor()
                return
        raise KeyError("Error: The entire hash table was searched, but no empty slot was found."
                       "Please inspect load factor expansion logic.")

    def search(self, pkg_id: int) -> Package:  # O(n)
        # Iteratively look at buckets until desired pkg or empty slot is found.
        # If everything is hashed uniquely, O(1) runtime.
        for i in range(self.db_size):
            key = self.__hashfunc(pkg_id + i)
            pkg: Package = self.db[key]
            if pkg is None:
                raise KeyError("Package id " + str(pkg_id) + " not found in database.")
            elif pkg != "tombstone" and pkg.pkg_id == pkg_id:
                return pkg
        # If execution reaches here, we've checked every possible hash key possible.
        raise KeyError("Package id " + str(pkg_id) + " was not found in database.")

    def remove(self, pkg_id):  # O(n)
        # Similar behavior to search, but bucket's contents are replaced with a tombstone
        # when the desired package is found.
        for i in range(self.db_size):
            key = self.__hashfunc(pkg_id + i)
            pkg = self.db[key]
            if pkg is None:
                raise KeyError("Package id " + str(id) + " not found in database.")
            elif pkg != "tombstone" and pkg.id == id:
                self.db[key] = "tombstone"
        # If execution reaches here, we've checked every possible hash key possible.
        raise KeyError("Package id " + str(id) + " was not found in database.")

    # This is meant to executed at any point after the database has been populated with all packages in the csv.
    # It will associate a package with other packages listed as dependencies in special notes. This effectively creates
    # an undirected graph amongst packages in the database whose "edges" we can traverse to map out packages
    # which must be loaded together.
    def link_dependencies(self):  # O(n^2)
        dependency_pattern = re.compile('Must be delivered with')
        pkg_id_pattern = re.compile('[0-9]+')
        for pkg in self.db:
            if pkg and dependency_pattern.match(pkg.special_notes):
                id_list = pkg_id_pattern.findall(pkg.special_notes)
                for pkg_id in id_list:
                    other_pkg = self.search(int(pkg_id))
                    pkg.dependencies.append(other_pkg)
                    other_pkg.dependencies.append(pkg)


# Represents a geographical location and pertinent metadata.
class Location:
    def __init__(self, loc_id, parent_graph, name, addr, zipcode, distances):  # O(n)
        self.loc_id = int(loc_id)
        self.parent_graph = parent_graph
        self.name = name
        self.addr = addr
        self.zipcode = zipcode
        # Refers to the shortest known path to this location from some arbitrary starting location used in Dijkstra_SP.
        self.shortest_known_path = sys.maxsize
        # Similarly, refers to the location preceding this one on the shortest path to this location from some arbitrary
        # location. Used in Dijkstra_SP.
        self.previous_location = None
        self.distances = []
        for distance in distances:
            if distance != '':
                self.distances.append(distance)
            else:
                break

    # Uses distance data contained within this location and others in the parent graph to determine the known distance
    # to another location. Note that this is not necessarily the *shortest* distance, merely the distance of a known
    # direct path to that location.
    def get_distance_to(self, location_id: int):  # O(1)
        # To avoid data duplication, the graph's structure mirrors that of the WGUPS Distance Table file:
        # Each location stores only distance values for previous entries in the graph, exploiting the bidirectional
        # nature of the data, and the fact that the distance table represents a full mesh graph.
        if location_id == self.loc_id:
            return 0
        # If the destination is a previous entry in the graph, the distance can be found in local "edge" list.
        if location_id < self.loc_id:
            return self.distances[location_id]
        # If the destination is a later entry in the graph, the distance can be found in that location's list.
        elif location_id > self.loc_id:
            return self.parent_graph[location_id].distances[self.loc_id]

    # Clears out the "shortest path" and "previous location" fields, as they are relative to whatever the starting
    # location is for the most recent run of Dijkstra_SP.
    def reset_path(self):  # O(1)
        self.shortest_known_path = sys.maxsize
        self.previous_location = None


# Represents a WGUPS delivery truck in terms of its basic characteristics, package load, and linked package database.
class Truck:
    def __init__(self, pkg_db, truck_id, location: Location, avg_speed=18,
                 capacity=16, mileage=0, dispatch_delay=0):  # O(1)
        self.truck_id = truck_id
        self.avg_speed = avg_speed
        self.capacity = capacity
        # In this scenario, WGUPS is so wealthy that their trucks are brand new - 0 mileage!
        self.mileage = mileage
        # This field represents the time in minutes that a truck is delayed from loading and going out for delivery.
        # It is meant to be used in the event that we want the truck to remain at the hub waiting for delayed packages.
        self.dispatch_delay = dispatch_delay
        self.db: PackageDB = pkg_db
        self.delivery_list = []
        self.location: Location = location

    # Calculates time of day for a given truck based on how far it has travelled at that point in time, also
    # accounting for a truck being dispatched later than the start of day to accommodate delayed packages.
    def current_time(self) -> datetime.datetime:  # O(1)
        time_since_day_start = datetime.timedelta(hours=self.mileage / self.avg_speed, minutes=self.dispatch_delay)
        return start_time_date + time_since_day_start

    # Need to update this once Dijkstra is working with logic for handling special notes & deadlines.
    # Optional arg "load_cap" can be used to load only up to a certain number of packages at once
    # (provided there are packages available to load and that the truck itself is not already full).
    def load(self, manif: List[Package], load_cap=sys.maxsize):  # O(n^2) - due to elif for p4 having loop.
        # Provided we have not exceeded capacity, and manifest isn't empty,
        # remove the next pkg from manifest, update it's load time, and "load" onto truck.
        counter = 0
        next_load: List[Package] = []
        while (len(self.delivery_list) < self.capacity) and manif and counter < load_cap:
            current_pkg = manif.pop(0)
            p1 = re.compile('Can only be on truck')
            p2 = re.compile('Delayed on flight')
            p3 = re.compile('Wrong address listed')
            if current_pkg.special_notes or current_pkg.dependencies:
                note: str = current_pkg.special_notes
                # If this package has to be loaded onto a particular truck, only load if this is the right truck.
                if p1.match(note):
                    tid = note[len(note) - 1: len(note)]
                    if self.truck_id == int(tid):
                        self.__load_pkg(current_pkg)
                        counter += 1
                    else:
                        next_load.append(current_pkg)
                # If the package is delayed, it can only be loaded once it has arrived at the depot.
                # If the package has the incorrect address listed, it's address has been updated preemptively during
                # insertion into the package database, and it's expected arrival time stored in package info. It is
                # then treated similarly to a delayed package.
                elif p2.match(note) or p3.match(note):
                    if current_pkg.time_available <= self.current_time():
                        self.__load_pkg(current_pkg)
                        counter += 1
                    else:
                        next_load.append(current_pkg)
                # If the package had delivery dependencies, we need to deliver package along with all dependencies.
                elif current_pkg.dependencies:
                    transitive_dependencies: List[Package] = []
                    discover_dependencies(current_pkg, self.db, transitive_dependencies)
                    if (len(self.delivery_list) + len(transitive_dependencies) <= self.capacity
                            and counter + len(transitive_dependencies) < load_cap):
                        for pkg in transitive_dependencies:  # O(n)
                            self.__load_pkg(pkg)
                            # Ensure that dependent packages are not considered for loading after being loaded.
                            if pkg is not current_pkg:
                                manif.remove(pkg)
                            counter += 1
                    else:
                        for pkg in transitive_dependencies:
                            next_load.append(pkg)
            # If the current_pkg bears no restrictions, simply load it and update our counter.
            else:
                self.__load_pkg(current_pkg)
                counter += 1
        # Restore ineligible or unavailable package to the top/front of the manifest. This way, they will be the first
        # to be considered the next time a truck is loaded (unless packages with deadlines must be delivered first).
        if next_load:
            for pkg in next_load:
                manif.insert(0, pkg)

    def __load_pkg(self, pkg: Package):  # O(1)
        pkg.load_time = self.current_time()
        self.delivery_list.append(pkg)

    def deliver(self, pkg: Package):  # O(1)
        pkg.delivery_time = self.current_time()
        print("Package #" + str(pkg.pkg_id) + " being delivered at " +
              datetime.datetime.strftime(pkg.delivery_time, "%H:%M"))


def main():  # O(n^4)
    # The program extracts relevant data from two csv files - one representing package data, and another representing
    # 'edges' between location 'nodes', both based upon the excel files provided by WGU. Both files must be in the same
    # directory as this script.
    # Translate raw package and location details into data structures we can operate on.
    print("Generating package manifest and location map...")
    try:
        graph = csv_to_graph("WGUPS Distance Table.csv")  # O(n^2)
        manifest = csv_to_manifest("WGUPS Package File.csv")  # O(n)
    except FileNotFoundError as e:
        print(e.args)
        sys.exit(1)

    print("Sorting manifest by delivery deadline to ensure timely delivery...")
    sort_by_delivery_priority(manifest)  # O(n^2)

    print("Generating package database and linking their respective destinations...")
    db = PackageDB(len(manifest))
    for package in manifest:  # O(n)
        db.insert(package)
        package.associate_destination(graph)

    print("Linking package dependencies...")
    db.link_dependencies()  # O(n^2)

    print("Calculating delivery solution. Delivery simulation begins now.\n")
    t1 = Truck(db, 1, graph[0])
    # Truck 2's load and departure from the hub is delayed to allow delayed packages with deadlines to be loaded
    # for delivery as soon as possible. To help facilitate timely delivery, Truck 2 also carries a smaller load to
    # help counter the delivery algorithm prioritizing delivery to the *nearest* location - if more packages onboard
    # are packages with deadlines, then it is more likely that the algorithm will select a package with a deadline.
    t2 = Truck(db, 2, graph[0], dispatch_delay=65)
    flag = True
    # Alternates loading and delivering of trucks, and written in a way that prevents us from trying to load
    # a truck if all packages have been delivered.
    while manifest:  # O(n*n^3) = O(n^4), yikes.
        if flag:
            t1.load(manifest)
            deliver_packages(t1, graph)
            flag = False
        else:
            t2.load(manifest, load_cap=10)
            deliver_packages(t2, graph)
            flag = True
    print("\nDelivery solution for all packages devised.")
    ui(db, t1, t2)  # O(n)

# Core Functions/Methods - implemented directly in main method. Listed in order of use.
# ======================================================================================================================


# The first 3 columns in the csv containing location data should, in order, should be name, addr, zip, followed by
# Entries for distances to other hubs. Note that although the csv is based entirely on the distance table xml provided
# by WGU, it is not enough to simply convert that file to a csv and then use that in this program. The csv used
# must be in same directory as the program.
def csv_to_graph(csv_name):  # O(n^2)
    g = []
    with open(csv_name, newline='') as distance_table:
        reader = csv.reader(distance_table)
        index = 0
        for entry in reader:  # O(n)
            distances = []
            for dist in entry[3:]:  # O(n)
                if not dist:
                    break
                else:
                    distances.append(float(dist))
            g.append(Location(index, g, entry[0], entry[1], entry[2], distances))  # O(1)
            index += 1
    return g


# Based on the WGUPS package xml provided by WGU in a similar fashion to csv_to_graph above.
def csv_to_manifest(csv_name) -> list:  # O(n)
    manif = []
    with open(csv_name, newline='') as manifest_csv:
        reader = csv.DictReader(manifest_csv)
        for pkg_entry in reader:
            pkg = Package(pkg_entry["Package ID"], pkg_entry["Address"], pkg_entry["City"],
                          pkg_entry["State"], pkg_entry["Zip"], pkg_entry["Delivery Deadline"],
                          pkg_entry["MassKG"], pkg_entry["Special Notes"])
            # If this package must be delivered with other packages, we will scan the string for numbes
            # representing those packages' IDs, which can then be associated with the package.
            manif.append(pkg)
    return manif


# Based on insertion sort algorithm. Ensures that trucks attempt to load packages with deadlines first.
def sort_by_delivery_priority(manifest: List[Package]):  # O(n^2)
    for i in range(1, len(manifest)):
        for j in range(i, 0, -1):
            deadline1 = manifest[j-1].delivery_deadline
            deadline2 = manifest[j].delivery_deadline
            # Four basic outcomes may result from comparison: If the deadlines are the same, whether they are EOD or
            # an actual time, we needn't do anything. On the other hand, if an EOD package is placed before a package
            # with a time deadline, this is obviously wrong and swap should occur. Similarly, packages with timed
            # deadlines should be swapped to be in ascending order of time.
            if not deadline1 == deadline2:
                if deadline1 == "EOD":
                    swap_with_previous(manifest, j)
                elif deadline2 != "EOD":
                    dt1 = datetime.datetime.strptime(deadline1, "%I:%M %p")
                    dt2 = datetime.datetime.strptime(deadline2, "%I:%M %p")
                    if dt1 > dt2:
                        swap_with_previous(manifest, j)


# Core delivery logic which implements a version of Dijstra's Shortest Path algorithm. Heuristically minimizes mileage
# by delivering whichever package is nearest to the truck's current location. It will do this until all packages onboard
# are delivered, and then take the shortest return path to the hub from it's current location.
def deliver_packages(t: Truck, g: List[Location]):  # O(n^3)
    destinations = []
    # Determine locations we must visit, and shortest path to each from truck's current location.
    for pkg in t.delivery_list:  # O(n)
        if pkg.destination not in destinations:
            destinations.append(pkg.destination)
    while destinations:  # O(n*n^2 + n*log(n) + n + n^2) = O(n^3)
        for destination in destinations:  # O(n)
            dijkstra_sp(g, t.location.loc_id, destination.loc_id)  # O(n^2)
        destinations.sort(key=lambda d: d.shortest_known_path)  # O(n*log(n))
        # Travel to the nearest location, update our location and mileage incurred by trip, deliver packages.
        t.location = destinations.pop(0)
        t.mileage += t.location.shortest_known_path
        print("")
        print("")
        print("Truck #" + str(t.truck_id) + " now travelling to " + t.location.name + ".")
        print("Odometer: " + str(t.mileage))
        print("")
        # The following code manages to delivery the appropriate packages without editing the list in place (which
        # causes a bug where a pkg is skipped if its predecessor is delivered) and without requiring an extra loop.
        # Updated_delivery_list contains packages that are NOT delivered yet.
        updated_delivery_list = []
        for pkg in t.delivery_list:  # O(n)
            if pkg.destination is t.location:
                t.deliver(pkg)
            else:
                updated_delivery_list.append(pkg)
        t.delivery_list = updated_delivery_list
    print("All destinations have been visited.")
    dijkstra_sp(g, t.location.loc_id, g[0].loc_id)  # O(n^2)
    # Note that g[0], the first location registered in our location graph, is assumed to be the hub.
    print("Truck #" + str(t.truck_id) + " returning to hub (" + g[0].name + ").")
    t.location = g[0]
    t.mileage += t.location.shortest_known_path
    print("Odometer: " + str(t.mileage))


# The user interface outputs the total projected mileage of all trucks incurred by the end of the day.
# It will also allow the user to request comprehensive status reports or info on any package in the database
# at any time during the day.
def ui(pkg_db: PackageDB, t1: Truck, t2: Truck):  # O(n) - while loop execution time depends on n # of queries by user.
    user_in: str = ''
    print("\nProjected mileage for trucks 1 and 2 at EOD are " +
          str(t1.mileage) + " and " + str(t2.mileage) + " respectively.")
    print("Total mileage projected for today's deliveries is: " + str(t1.mileage + t2.mileage) + ".")
    print("To fetch a delivery status report for all packages at a given time, "
          "enter the time of day using the following format: HH:MM.\n"
          "To fetch the info and delivery status of an individual package at a given time,"
          "enter its package ID followed by the the time of day in the following format: 'HH:MM,ID'\n"
          "To exit the program, type 'exit'.")
    while user_in != 'exit':
        user_in = input()
        p1 = re.compile('[0-2][0-9]:[0-5][0-9]')
        # First, verify that hour and minute are valid values in the appropriate format.
        if p1.match(user_in) is not None:
            hr_and_min = (user_in[0:5]).split(':')
            if int(hr_and_min[0]) <= 24 and int(hr_and_min[1]) <= 59:
                p2 = re.compile('[0-2][0-9]:[0-5][0-9],[0-9]+')
                # Now, determine course of action based on presence or absence of a package ID.
                # Case A: A package ID is present, so we should use it's status method.
                if p2.fullmatch(user_in) is not None:
                    pkg_id = int((user_in.split(','))[1])
                    try:
                        status_time = datetime.datetime.strptime((user_in.split(','))[0], "%H:%M")
                        status_datetime = datetime.datetime.combine(datetime.datetime.today(), status_time.time())
                        pkg = pkg_db.search(pkg_id)
                        pkg.info()
                        pkg.status(status_datetime)
                    except KeyError as e:
                        print(e.args)
                # Case B: A package ID is not present, so we're being asked to print out a status report.
                elif p1.fullmatch(user_in) is not None:
                    status_time = datetime.datetime.strptime(user_in, "%H:%M")
                    status_datetime = datetime.datetime.combine(datetime.datetime.today(), status_time.time())
                    pkg_db.status_report(status_datetime)
                else:
                    print("Invalid input. Please try again.")
            else:
                print("Invalid input. Please try again.")
        elif user_in == 'exit':
            print("Exiting program.")
        else:
            print("Invalid input. Please try again.")


# Helper Functions/Methods - used within core functions/methods and other helper functions/methods.
# ======================================================================================================================


# Small helper function to convert strings of the form "HH:MM" to a datetime object for today's date.
# Also works for strings of the form "H:MM".
def str_to_datetime(timestr: str):  # O(1)
    t = datetime.datetime.strptime(timestr, "%H:%M")
    return datetime.datetime.combine(datetime.datetime.today(), t.time())


# Used in the event that a package's address is known to be incorrect.
def update_pkg_addr(pkg):  # O(n)
    updated_address = input("What is the correct address?\n")
    pkg.address = updated_address
    updated_city = input("What is the correct city?\n")
    pkg.city = updated_city
    updated_state = input("What is the correct state?\n")
    pkg.state = updated_state
    updated_zipcode = input("What is the updated zipcode?\n")
    pkg.zipcode = updated_zipcode


# Used in the event that a package is known to be delayed, and thus unavailable for loading at the hub.
def update_time_available(pkg, input_prompt: str):  # O(1)
    time_pattern = re.compile('[0-2][0-9]:[0-5][0-9]')
    time_pattern2 = re.compile('[0-9]:[0-5][0-9]')
    for input_attempt in range(3):
        try:
            print("Special circumstance detected for package ID " + str(pkg.pkg_id) + " -> ", end="")
            timestr = input(input_prompt)
            if not (time_pattern.fullmatch(timestr) or time_pattern2.fullmatch(timestr)):
                raise ValueError("Invalid time format. Must be of format 'HH:MM' or 'H:MM'.\n")
            else:
                pkg.time_available = str_to_datetime(timestr)
                break
        except ValueError as e:
            print(e)
            if input_attempt == 2:
                raise ValueError("Invalid time format. Max attempts exceeded. System shutting down.")


# Recursively checks and tracks a package's known dependencies (packages that must be loaded onto the same truck)
# for any dependencies *they* in turn may have. This must be done because package dependencies are 1-to-1 and
# transitive: e.g., If package 1 has to be loaded with package 3, it follows that the converse is true.
# If package 1 must be loaded with package 3, and package 3 must be loaded with package 5, then it follows that
# package 1 must be loaded with package 5.
def discover_dependencies(pkg, pkg_db, transitive_dependencies):  # O(n^2)
    if pkg not in transitive_dependencies:
        transitive_dependencies.append(pkg)
        if pkg.dependencies:
            for other_pkg in pkg.dependencies:  # O(n)
                # Also O(n) as the recursive call may continue any number of time before reaching base case.
                discover_dependencies(other_pkg, pkg_db, transitive_dependencies)


# Based on Dijkstra Shortest Path algorithm.
def dijkstra_sp(g: list, start_loc_id, dest_id):  # O(n^2) - higher time complexity due to insertion sort (sort_by_dist)
    unvisited = []
    # Extract all locations from graph and enqueue to be visited, then sort by proximity to start location.
    for loc in g:  # O(n)
        loc.reset_path()
        unvisited.append(loc)
    # start has 0 dist from itself, and will be the first location to be visited.
    g[start_loc_id].shortest_known_path = 0
    sort_by_dist_ascending(unvisited, g[start_loc_id])  # O(n^2)
    while unvisited:  # O(n) - time complexity governed by number of locations in graph and destination.
        # Visit closest destination until we have reached the destination specified by dest_id.
        current_loc = unvisited.pop(0)
        if current_loc.loc_id == dest_id:
            break
        for loc in unvisited:
            distance = current_loc.get_distance_to(loc.loc_id)
            alt_path = current_loc.shortest_known_path + distance
            if alt_path < loc.shortest_known_path:
                loc.shortest_known_path = alt_path
                loc.previous_location = current_loc
    print("The shortest known path to " + g[dest_id].name + " from " + g[start_loc_id].name + " is "
          + str(g[dest_id].shortest_known_path) + " miles.")
    print_path(g[dest_id])


# Based on insertion sort algorithm.
def sort_by_dist_ascending(locations, origin: Location):  # O(n^2)
    for i in range(1, len(locations)):
        for j in range(i, 0, -1):
            if locations[j-1].get_distance_to(origin.loc_id) > locations[j].get_distance_to(origin.loc_id):
                # Swap indices of locations.
                swap_with_previous(locations, j)


# Swaps previous item with the item at the provided index (j).
def swap_with_previous(li: list, j: int):  # O(1)
    temp = li[j - 1]
    li[j - 1] = li[j]
    li[j] = temp


# Traces path of given location back to the origin location, and stores path (in order of first to last location
# visited) in the empty list passed in.
def trace_path(loc: Location, path: list):  # O(n) - Recursively calls itself n times prior to base case.
    path.append(loc)
    # Now, if there is a previous location, it should be asked to add itself to the path (recursive step)
    if loc.previous_location:
        trace_path(loc.previous_location, path)
    # If there isn't, we have reached the origin, and we should reverse the list so it reads
    # from startpoint to endpoint.
    else:
        path.reverse()  # O(n)


# Outputs the provided path in a user friendly fashion to the console.
def print_path(loc: Location):  # O(n)
    path = []
    trace_path(loc, path)
    for i in range(len(path)):
        if i == (len(path) - 1):
            print(path[i].name)
        else:
            print(path[i].name + " --> ", end='')


if __name__ == '__main__':
    main()
