
import sys
import os
import libvirt
from typing import Callable, TypeAlias
from enum import Enum
from xml.etree import ElementTree as ET

snapshotDirectory: str = "/var/lib/libvirt/images"
libvirtURI: str = "qemu:///system"
connType: TypeAlias = libvirt.virConnect
domainType: TypeAlias = libvirt.virDomain
snapshotType: TypeAlias = libvirt.virDomainSnapshot

class Action(Enum):
	LIST	= 0
	CREATE	= 1
	REVERT	= 2
	DELETE	= 3
	EXIT	= 4

action2str: dict[Action, str] = {
	Action.LIST:	"List snapshots",
	Action.CREATE:	"Create snapshot",
	Action.REVERT:	"Revert snapshot",
	Action.DELETE:	"Delete snapshot",
	Action.EXIT:	"Exit",
}

class SnapshotChoice(Enum):
	NO_SNAPSHOTS_FOUND	= 0
	REVERT_TO_ORIGINAL	= 1

def checkRoot():
	if os.geteuid() != 0:
		print("Warning: non-root user might not have access to the libvirt API", file=sys.stderr)

def checkDomains(conn: connType):
	if len(conn.listAllDomains()) < 1:
		print("Error: no domains found", file=sys.stderr)

def userConfirm(msg: str, default: bool) -> bool:
	while True:
		print()
		userInput: str = input(msg)
		if len(userInput) < 1:
			return default
		elif len(userInput) == 1:
			if userInput[0].lower() == "y":
				return True
			if userInput[0].lower() == "n":
				return False

def inputInt(start: int, end: int) -> int:
	while True:
		strInput: str = input("Enter number in range [{:d}-{:d}]: ".format(start, end))
		try:
			intInput: int = int(strInput)
			if start <= intInput <= end:
				return intInput
			else:
				print("Entered number is not in range", file=sys.stderr)
		except ValueError:
			print("Input is not an integer", file=sys.stderr)

def menu(options: list[str]) -> int:
	if len(options) < 1:
		print("Error: no options available", file=sys.stderr)
		return 0
	for i, option in enumerate(options):
		print("\t[{:d}]: {:s}".format(i + 1, option))
	return (inputInt(start=1, end=len(options)) - 1)

def menuAction(conn: connType) -> Action:
	print()
	print("Select an action:")
	return Action(menu(list(action2str.values())))

def menuDomain(conn: connType) -> domainType|None:
	domains: list[domainType] = conn.listAllDomains()
	print()
	print("Select a domain:")
	domainNames: list[str] = [domain.name() for domain in domains]
	domain: domainType = domains[menu(domainNames)]
	if domain.isActive():
		print("WARNING: domain is currently active", file=sys.stderr)
		if not userConfirm(msg="Continue anyways? [y/N]: ", default=False):
			return None
	return domain

def menuDisk(domain: domainType) -> ET.Element:
	tree = ET.fromstring(domain.XMLDesc(0))
	blockDevices = []
	for target in tree.findall("devices/disk"):
		blockDevice: str = ""
		blockDevice += str(target.findall("source")[0].get("file")) + ", "
		blockDevice += str(target.findall("driver")[0].get("type")) + ", "
		blockDevice += str(target.findall("target")[0].get("dev"))
		blockDevices.append(blockDevice)
	diskIndex = menu(blockDevices)
	diskXml: ET.Element = tree.findall("devices/disk")[diskIndex]
	return diskXml

def menuSnapshots(domain: domainType, snapshots: list[snapshotType] = []) -> snapshotType|SnapshotChoice:
	if len(snapshots) < 1:
		snapshots = domain.listAllSnapshots()
	if len(snapshots) < 1:
		print("Error: no snapshots found for selected domain", file=sys.stderr)
		return SnapshotChoice.NO_SNAPSHOTS_FOUND
	snapshotNames: list[str] = [snapshot.getName() for snapshot in snapshots] + ["Original image (external only)"]
	userChoice: int = menu(snapshotNames)
	snapshot: snapshotType
	if userChoice == len(snapshots):
		return SnapshotChoice.REVERT_TO_ORIGINAL
	else:
		return snapshots[userChoice]

def findRoots(snapshots: list[snapshotType]) -> set[snapshotType]:
	children: set[str] = set()
	roots: set[snapshotType] = set()
	for snapshot in snapshots:
		children = children.union([c.getName() for c in snapshot.listAllChildren()])
	for snapshot in snapshots:
		if snapshot.getName() not in children:
			roots.add(snapshot)
	return roots

def actionList(domain: domainType):
	for (flags, typeStr) in [(libvirt.VIR_DOMAIN_SNAPSHOT_LIST_EXTERNAL, "External"), (libvirt.VIR_DOMAIN_SNAPSHOT_LIST_INTERNAL, "Internal")]:
		snapshots: list[snapshotType] = domain.listAllSnapshots(flags=flags)
		roots: set[snapshotType] = findRoots(snapshots)
		print()
		print("{:s}: ".format(typeStr))
		print(" Current |    Name    |   Parent   ")
		print("---------+------------+------------")
		for snapshot in snapshots:
			current: str = "*" if snapshot.isCurrent() else " "
			name: str = snapshot.getName()
			parent: str = snapshot.getParent().getName() if snapshot not in roots else "    -     "
			print("    {:1s}    | {:10s} | {:10s} ".format(current, name, parent))

def actionCreate(domain: domainType):

	# root
	print()
	print("Select snapshot type: ")
	internal: bool = bool(menu(["External (recommended)", "Internal"]))
	xmlRoot = ET.Element("domainsnapshot")
	
	# name
	xmlName = ET.SubElement(xmlRoot, "name")
	print()
	while xmlName.text is None or len(xmlName.text) < 1:
		xmlName.text = input("Enter snapshot name: ")

	# desc
	print()
	descText = input("Enter snapshot description (optional): ")
	if len(descText) > 0:
		xmlDesc = ET.SubElement(xmlRoot, "description")
		xmlDesc.text = descText

	flags: int = 0
	if not internal:
		flags |= libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_DISK_ONLY
		disk: ET.Element = menuDisk(domain)
		xmlDisks: ET.Element = ET.SubElement(xmlRoot, "disks")
		xmlDisk: ET.Element = ET.SubElement(xmlDisks, "disk", name=str(disk.findall("target")[0].get("dev")), snapshot="external")

	xmlStr: str = ET.tostring(xmlRoot).decode()
	domain.snapshotCreateXML(xmlStr, flags=flags)
	print("Successfully created snapshot \"{:s}\" for domain \"{:s}\"".format(xmlName.text, domain.name()))

def actionDelete(domain: domainType):
	print()
	print("Select snapshot to delete: ")
	snapshotsExternal: set[snapshotType] = set(domain.listAllSnapshots(libvirt.VIR_DOMAIN_SNAPSHOT_LIST_EXTERNAL))
	snapshotsInternal: set[snapshotType] = set(domain.listAllSnapshots(libvirt.VIR_DOMAIN_SNAPSHOT_LIST_INTERNAL))
	snapshots: list[snapshotType] = list(snapshotsExternal.union(snapshotsInternal))
	snapshot: snapshotType|SnapshotChoice = menuSnapshots(domain, snapshots=snapshots)
	match snapshot:
		case SnapshotChoice.NO_SNAPSHOTS_FOUND | SnapshotChoice.REVERT_TO_ORIGINAL:
			pass
		case _:
			if snapshot in snapshotsExternal:
				snapshot.delete(libvirt.VIR_DOMAIN_SNAPSHOT_DELETE_METADATA_ONLY)
				os.remove("{:s}/{:s}.{:s}".format(snapshotDirectory, domain.name(), snapshot.getName()))
			elif snapshot in snapshotsInternal:
				snapshot.delete()
			else:
				print("Error: failed to determine snapshot type", file=sys.stderr)

def actionRevertExternal(domain: domainType, snapshotName: str):
	xmlDisk: ET.Element = menuDisk(domain)
	src: ET.Element|None = xmlDisk.find("source")

	if src is not None:
		path: str|None = src.get("file")
		if path is not None:
			newPath: str = "{:s}/{:s}.{:s}".format(snapshotDirectory, domain.name(), snapshotName)
			if os.path.isfile(newPath):
				src.set("file", newPath)
				print("Successfully reverted domain \"{:s}\" to snapshot \"{:s}\"".format(domain.name(), snapshotName))
			else:
				print("Error: could not find snapshot disk file", file=sys.stderr)
				print("Full path: " + newPath, file=sys.stderr)
				return
		else:
			print("Error: could not get disk source path", file=sys.stderr)
			return
	else:
		print("Error: could not find disk source", file=sys.stderr)
		return

	xmlStr: str = ET.tostring(xmlDisk).decode()
	domain.updateDeviceFlags(xmlStr)

def actionRevert(domain: domainType):
	print()
	print("Select snapshot to revert to: ")
	snapshotsExternal: set[snapshotType] = set(domain.listAllSnapshots(libvirt.VIR_DOMAIN_SNAPSHOT_LIST_EXTERNAL))
	snapshotsInternal: set[snapshotType] = set(domain.listAllSnapshots(libvirt.VIR_DOMAIN_SNAPSHOT_LIST_INTERNAL))
	snapshots: list[snapshotType] = list(snapshotsExternal.union(snapshotsInternal))
	snapshot: snapshotType|SnapshotChoice = menuSnapshots(domain, snapshots)
	match snapshot:
		case SnapshotChoice.NO_SNAPSHOTS_FOUND:
			pass
		case SnapshotChoice.REVERT_TO_ORIGINAL:
			actionRevertExternal(domain, snapshotName="qcow2")
		case _:
			if snapshot in snapshotsExternal:
				actionRevertExternal(domain, snapshotName=snapshot.getName())
			elif snapshot in snapshotsInternal:
				domain.revertToSnapshot(snapshot)
			else:
				print("Error: failed to determine snapshot type", file=sys.stderr)

def action2fun(conn: connType, action: Action) -> Callable[[domainType], None]:
	match action:
		case Action.LIST:
			return actionList
		case Action.CREATE:
			return actionCreate
		case Action.REVERT:
			return actionRevert
		case Action.DELETE:
			return actionDelete
		case Action.EXIT:
			conn.close()
			exit(0)
			return lambda x: None

def main():
	checkRoot()
	conn: connType = libvirt.open(libvirtURI)
	checkDomains(conn)
	while True:
		domain: domainType|None = menuDomain(conn)
		if domain is None:
			continue
		action: Action = menuAction(conn)
		actionFun: Callable[[domainType], None] = action2fun(conn, action)
		actionFun(domain)

main()
