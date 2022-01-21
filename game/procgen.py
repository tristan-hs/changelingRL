from __future__ import annotations

import random
from typing import Iterator, List, Tuple, TYPE_CHECKING, Iterable

import tcod
import numpy
import copy
import random
import math

from game.entity import Item

from game import entity_factories, tile_types
from game.game_map import GameMap
from game.render_functions import DIRECTIONS
from game.components.ai import PeeNPC
from game.components.status_effect import KeyHolder

if TYPE_CHECKING:
	from game.engine import Engine


class Room:
	closet = False

	def __init__(self, x: int, y: int, map_width: int, map_height: int, dungeon, name:str=''):
		self.seed = (x,y)
		self.tiles = [self.seed]
		self.map_width = map_width
		self.map_height = map_height
		self.rooms = dungeon.rooms
		self.name = name
		self.dungeon = dungeon

	def finalize(self):
		for tile in self.inner:
			self.dungeon.tiles[tile] = tile_types.floor
		self.dungeon.rooms.append(self)

class MainHall(Room):
	def __init__(self,map_width,map_height,dungeon):
		super().__init__(*self.generate_seed(map_width,map_height,dungeon),map_width,map_height,dungeon)
		self.name = "Main Hall"
		self.generate()

		if not hasattr(self,"parent"):
			for i in range(3):
				h = AuxHall(map_width,map_height,dungeon,self)
				h.finalize()

	def generate_seed(self, mw, mh, d):
		return (mw//2, mh//2)

	def generate(self):
		directions = [[0,1],[0,-1],[-1,0],[1,0]]
		random.shuffle(directions)
		for i in range(4):
			if i > 0 and random.random() > 0.5:
				continue
			
			growth_dir = directions[i]
			growth_axis = 0 if growth_dir[0] != 0 else 1
			static_axis = 0 if growth_axis == 1 else 0

			width = random.choice([2,3,4]) if i > 0 else 4
			x,y = self.seed

			length_limit = 13
			length = random.choice(range(width,length_limit)) if i > 0 else random.choice(range(9,15))

			x_range = (x-2,x-2+width) if growth_axis == 1 else (x,x+(length*growth_dir[0]))
			y_range = (y-2,y-2+width) if growth_axis == 0 else (y,y+(length*growth_dir[1]))

			x_range = (x_range[1],x_range[0]) if x_range[0] > x_range[1] else x_range
			y_range = (y_range[1],y_range[0]) if y_range[0] > y_range[1] else y_range

			for x in range(*x_range):
				for y in range(*y_range):
					tile = (x,y)
					if tile not in self.tiles and self.dungeon.in_bounds(*tile) and 0 not in tile and tile[0] != self.map_width-1 and tile[1] != self.map_height-1:
						self.tiles.append(tile)

	@property
	def center(self):
		return self.seed

	@property
	def inner(self):
		return self.tiles

class AuxHall(MainHall):
	def __init__(self,map_width,map_height,dungeon,hall):
		self.parent = hall
		super().__init__(map_width,map_height,dungeon)

	# get a tile 1 off from the main hall
	def generate_seed(self,map_width,map_height,dungeon):
		while True:
			t = random.choice(self.parent.tiles)
			permutations = [(t[0],t[1]+1),(t[0],t[1]-1),(t[0]+1,t[1]),(t[0]-1,t[1])]
			random.shuffle(permutations)
			for p in permutations:
				if p not in self.parent.tiles:
					return p
		return tile

	def finalize(self):
		self.dungeon.upstairs_location = self.center
		self.parent.tiles = list(set(self.parent.tiles).union(set(self.tiles)))

class MainRoom(Room):
	min_size = 3
	max_size = 7

	def __init__(self,map_width,map_height,dungeon,parent):
		self.parent = parent
		self.dungeon = dungeon

		self.valid = False
		self.seed = None
		self.find_seed()
		if not self.seed:
			return

		super().__init__(self.seed[0],self.seed[1],map_width,map_height,dungeon)

		self.generate()

	def add_closet(self):
		attempts = 50
		for i in range(attempts):
			closet = Closet(self.map_width,self.map_height,self.dungeon,self)
			if closet.valid:
				closet.finalize()
				initials = ''.join([word[0] for word in self.name.split(' ')])
				suffix = random.choice([" Toilet"])
				closet.name = initials + suffix
				break

	@property
	def inner(self):
		return [tile for tile in self.tiles if tile[0] not in [self.x1,self.x2] and tile[1] not in [self.y1,self.y2] ]

	def finalize(self):
		super().finalize()
		self.dungeon.tiles[self.sprout] = tile_types.door

	def find_seed(self):
		attempts = 50
		for i in range(attempts):
			if i == attempts:
				raise Exception("No seed found")
			seed = random.choice(self.parent.tiles)
			sprouts = []
			for d in DIRECTIONS:
				if abs(d[0]) == abs(d[1]):
					continue
				sprout = (seed[0]+d[0],seed[1]+d[1])
				if any(sprout in room.tiles for room in self.dungeon.rooms):
					continue
				sprouts.append(sprout)
			if not sprouts:
				continue
			self.seed = seed
			self.sprout = random.choice(sprouts)
			break

	def generate(self):
		forbidden_dir = (self.seed[0]-self.sprout[0],self.seed[1]-self.sprout[1])

		ce = -1

		sap = (self.sprout[0] + (forbidden_dir[0]* ce), self.sprout[1] + (forbidden_dir[1]* ce))
		
		for room in self.dungeon.rooms:
			if sap in room.tiles:
				return

		x1 = x2 = self.sprout[0]
		y1 = y2 = self.sprout[1]
		tiles = [sap]

		min_size = self.min_size
		max_size = self.max_size
		attempts = 0

		while (x2-x1 < max_size or y2-y1 < max_size) and attempts < 100:
			attempts += 1

			potential_dirs = [d for d in DIRECTIONS if d != forbidden_dir and abs(d[0]) != abs(d[1]) and (d[0] == 0 or x2-x1 < max_size) and (d[1] == 0 or y2-y1 < max_size)]
			random.shuffle(potential_dirs)

			grew = False

			for d in potential_dirs:
				nx1 = x1 if d[0] > -1 else x1-1
				nx2 = x2 if d[0] < 1 else x2+1
				ny1 = y1 if d[1] > -1 else y1-1
				ny2 = y2 if d[1] < 1 else y2+1

				if nx1 < 1 or nx2 > self.map_width-3 or ny1 < 1 or ny2 > self.map_height-3:
					continue

				new_tiles = []
				for x in range(nx1,nx2+1):
					for y in range(ny1,ny2+1):
						new_tiles.append((x,y))

				def check_tiles(ts):
					for room in self.dungeon.rooms:
						for t1 in ts:
							if t1 in room.tiles:
								return False
					return True

				if not check_tiles(new_tiles):
					continue

				def next_to(tile1,tile2):
					if abs(tile1[0]-tile2[0]) < 2 and abs(tile1[1]-tile2[1]) < 2:
						return True
					return False

				def check_adjacency():
					rooms = [r for r in self.dungeon.rooms if r.closet or r.name == "Main Hall"]
					for r in rooms:
						for t1 in r.tiles:
							for t2 in new_tiles:
								if next_to(t1,t2):
									return False
					return True

				if self.closet and not check_adjacency():
					continue

				tiles = new_tiles
				x1,x2,y1,y2 = (nx1,nx2,ny1,ny2)
				grew = True
				break

			if not grew:
				break

			if self.closet and (x2-x1 >= min_size or y2-y1 >= min_size) and x2-x1 > 0 and y2-y1 > 0:
				break

			if not self.closet and x2-x1 > min_size and y2-y1 > min_size and random.random() < 0.29:
				break

		if x2-x1 > min_size and y2-y1 > min_size or (self.closet and (x2-x1 >= min_size or y2-y1 >= min_size) and x2-x1 > 0 and y2-y1 > 0):
			self.valid = True
			self.tiles = tiles
			self.x1,self.x2,self.y1,self.y2 = (x1,x2,y1,y2)
			if self.closet:
				self.sprout = self.seed

class ShuttleRoom(MainRoom):
	min_size = 11
	max_size = 15

	def finalize(self):
		super().finalize()
		for tile in self.evac_area:
			self.dungeon.tiles[tile] = tile_types.evac_area
		for tile in self.fence:
			self.dungeon.tiles[tile] = tile_types.wall
		self.dungeon.tiles[self.gate] = tile_types.locked_gate
		self.dungeon.tiles[self.bioscanner] = tile_types.bioscanner
		self.dungeon.shuttle = self

	def generate(self):
		super().generate()
		if not self.valid:
			return

		xdiff = self.x2 - self.x1
		ydiff = self.y2 - self.y1
		halves = [
			(self.x1,self.x2 - (xdiff//2),self.y1,self.y2),
			(self.x1 + (xdiff//2),self.x2,self.y1,self.y2),
			(self.x1,self.x2,self.y1+(ydiff//2),self.y2),
			(self.x1,self.x2,self.y1,self.y2-(ydiff//2))
		]

		halves = [h for h in halves if self.sprout[0] not in [h[0],h[1]] and self.sprout[1] not in [h[2],h[3]]]
		if not len(halves):
			self.valid = False
			return

		half = random.choice(halves)

		evac = []
		for x in range(half[0]+1,half[1]):
			for y in range(half[2]+1,half[3]):
				evac.append((x,y))

		self.evac_area = evac

		fence = list(half)
		for i,c in enumerate([self.x1,self.x2,self.y1,self.y2]):
			if c != half[i]:
				counterpart = {0:1,1:0,2:3,3:2}[i]
				fence[counterpart] = half[i]

				if i in [1,3]:
					fence[i] += 1
					fence[counterpart] -= 1
				else:
					fence[i] -= 1
					fence[counterpart] += 1


		self.fence = []
		for x in range(fence[0]+1,fence[1]):
			for y in range(fence[2]+1,fence[3]):
				self.fence.append((x,y))

		gate_i = random.choice(range(len(self.fence)))
		self.gate = self.fence.pop(gate_i)

		bio_i = random.choice([i for i in [gate_i-1,gate_i] if i > -1 and i < len(self.fence)])
		self.bioscanner = self.fence.pop(bio_i)

		self.lobby = set(self.inner)
		for i in [self.evac_area,self.fence]:
			self.lobby -= set(i)
		self.lobby -= set([self.bioscanner,self.gate])
		self.lobby = list(self.lobby)


class Closet(MainRoom):
	min_size = 1
	max_size = 1
	closet = True

	@property
	def inner(self):
		return self.tiles



def generate_dungeon(floor_number, map_width, map_height, engine, game_mode, items):

	dungeon = GameMap(engine, map_width, map_height, floor_number, entities=[engine.player], items=[], game_mode=game_mode)
	
	hall = MainHall(map_width,map_height,dungeon)
	hall.finalize()

	attempts = 1000
	for i in range(attempts):
		h = hall
		shuttle = ShuttleRoom(map_width,map_height,dungeon,h)
		if not shuttle.valid:
			continue
		shuttle.name = "Shuttle"
		shuttle.finalize()
		break

	if not shuttle.valid:
		return generate_dungeon(floor_number,map_width,map_height,engine,game_mode,items)

	room_names = ["Bunks","Cafeteria","Engine","Bridge","Observation Deck","Lab","Rec Room","Holohall","Workshop","Green Room","Salon","Terrarium","Gym","Pressurizer","Quantum Effigy","HR Office","Storage Room","Launchpad","Gunnery","Greenhouse","Kitchen","Chapel","Incident Room","Sprobble Nook"]
	random.shuffle(room_names)

	room_number = random.choice(range(10,15))
	main_rooms = []
	for i in range(room_number):
		attempts = 1000 - (i*i*2)
		for i in range(attempts):
			h = hall
			room = MainRoom(map_width,map_height,dungeon,h)
			if not room.valid:
				continue

			room.name = room_names.pop()
			room.finalize()
			if random.random() < 0.45:
				room.add_closet()
			main_rooms.append(room)
			break
	
	toilets = [room for room in dungeon.rooms if room.closet]
	if len(toilets) < len(main_rooms)/4:
		return generate_dungeon(floor_number,map_width,map_height,engine,game_mode,items)

	if len(main_rooms) < 9:
		return generate_dungeon(floor_number,map_width,map_height,engine,game_mode,items)

	starting_toilet = random.choice(toilets)
	place_player(dungeon,random.choice(starting_toilet.inner),engine.player)

	toilet_tiles = starting_toilet.inner
	random.shuffle(toilet_tiles)
	for tile in toilet_tiles:
		if tile != dungeon.engine.player.xy:
			npc = entity_factories.NPC.spawn(dungeon,*tile)
			npc.last_peed = 0
			break

	NPC_number = math.floor(len(dungeon.rooms)*1.7)
	for i in range(NPC_number):
		room = random.choice([room for room in dungeon.rooms if room.name != "Shuttle" and not room.closet])
		tiles = room.inner
		random.shuffle(tiles)
		for tile in tiles:
			if any(entity.xy == tile for entity in dungeon.entities):
				continue
			entity_factories.NPC.spawn(dungeon,*tile)
			break

	a_by_d = dungeon.actors
	a_by_d.sort(key=lambda x: x.distance(*engine.player.xy))
	kh1 = a_by_d[-1]
	#kh2 = a_by_d[-2]
	KeyHolder(kh1)
	#KeyHolder(kh2)

	return dungeon

def place_player(dungeon,xy,player):
	player.place(*xy,dungeon)
	player.changeling_form = True
