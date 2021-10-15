"""Referential Sieve Player
"""

from hanabi_classes import *
from bot_utils import is_cardname_playable as is_playable
from copy import deepcopy

class ReferentialSievePlayer(AIPlayer):

    @classmethod
    def get_name(cls):
        return 'ref_sieve'

    def __init__(self, *args):
        """Can be overridden to perform initialization, but must call super"""
        super(ReferentialSievePlayer, self).__init__(*args)

    def play(self, r):
        r.HandHistory.append([newest_to_oldest(deepcopy(hand.cards)) for hand in r.h])
        recent_actions = r.playHistory[-r.nPlayers:]
        if len(recent_actions) < r.nPlayers:
            self.global_understanding = GlobalUnderstanding()
        initial_actor = r.whoseTurn - len(recent_actions)
        for i, action in enumerate(recent_actions):
            actor = (initial_actor + i + r.nPlayers) % r.nPlayers
            action_type, action = action
            if action_type == 'play':
                self.global_understanding.play(actor, action["name"], action["position"] - 1)
            elif action_type == 'discard':
                self.global_understanding.discard(actor, action["name"], action["position"] - 1)
            elif action_type == 'hint':
                receiver, value = action
                hands_at_time = r.HandHistory[-len(recent_actions) + i]
                touching = get_touching(hands_at_time[receiver], value)
                self.global_understanding.clue(receiver, value, touching)

        best_move = find_best_move(r.HandHistory[-1], r.whoseTurn, self.global_understanding)
        print('best_move', best_move, [card["name"] for card in r.HandHistory[-1][1]])
        return best_move


    def end_game_logging(self):
        """Can be overridden to perform logging at the end of the game"""
        pass

# Move selection
# 1. If there are no clues tokens, skip ahead
# 2. If my partner's chop is critical and at risk, try to give a clue
# 3. If I have a known play, play it
# 4. If there are 8 clues, give an 8 clue stall
# 5. If I am locked, give a locked hand stall
# 6. If I have a known trash, discard it
# 7. Otherwise, discard chop

def find_best_move(hands, player, global_understanding):
    partner = (player + 1) % 2
    current_max_score = global_understanding.max_score_adjusted()
    simulation = deepcopy(global_understanding)
    simulation.make_expected_move(partner, hands[partner])
    baseline_max_score = simulation.max_score_adjusted()

    my_identified_plays = global_understanding.get_identified_plays(global_understanding.hand_possibilities[player])
    best_play_slot = None
    best_play_score = 0
    for slot, identity in my_identified_plays:
        simulation = deepcopy(global_understanding)
        simulation.play(player, identity, slot)
        simulation.make_expected_move(partner, hands[partner])
        score = simulation.max_score_adjusted()
        if score > best_play_score:
            best_play_slot = slot
            best_play_score = score
    
    if best_play_slot == None and global_understanding.instructed_plays[player]:
        print('including instructed play')
        best_play_slot = global_understanding.instructed_plays[player][0]
        best_play_score = baseline_max_score

    if best_play_score == current_max_score:
        return 'play', hands[player][best_play_slot]

    best_clue = None
    best_clue_score = 0
    best_clue_strikes = 3
    if global_understanding.clue_tokens >= 1:
        for clue_value, touching in get_possible_clues(hands[partner]):
            simulation = deepcopy(global_understanding)
            simulation.clue(partner, clue_value, touching)
            simulation.make_expected_move(partner, hands[partner])
            score = simulation.max_score_adjusted()
            print('simulated', clue_value, score)
            if score > best_clue_score:
                best_clue = clue_value
                best_clue_score = score
                best_clue_strikes = simulation.strikes
            elif score == best_clue_score and simulation.strikes < best_clue_strikes:
                best_clue = clue_value
                best_clue_strikes = simulation.strikes

    if global_understanding.clue_tokens == 8:
        if best_clue_score > best_play_score:
            return 'hint', (partner, best_clue)
        else:
            return 'play', hands[player][best_play_slot]

    simulation = deepcopy(global_understanding)
    simulation.clue_tokens += 1
    simulation.make_expected_move(partner, hands[partner])
    discard_score = simulation.max_score_adjusted()
    best_discard = None

    if global_understanding.instructed_trash[player]:
        best_discard = global_understanding.instructed_trash[player][0]
    else:
        known_trashes = global_understanding.get_known_trashes(global_understanding.hand_possibilities[player])
        if known_trashes:
            best_discard = known_trashes[0]
        elif global_understanding.instructed_chop[player] != None:
            best_discard = global_understanding.instructed_chop[player]
        else:
            if global_understanding.instructed_to_lock[player] or best_play_slot != None:
                discard_score = 0
            unclued = get_unclued(global_understanding.hand_possibilities[player])
            if unclued:
                best_discard = unclued[0]
            else:
                best_discard = 0

    if best_clue_score > discard_score:
        return 'hint', (partner, best_clue)

    return 'discard', hands[player][best_discard]

def get_possible_clues(hand):
    clues = []
    for suit in VANILLA_SUITS:
        touching = get_touching(hand, suit)
        if touching:
            clues.append((suit, touching))
    for rank_int in range(1, 6):
        rank = str(rank_int)
        touching = get_touching(hand, rank)
        if touching:
            clues.append((rank, touching))
    return clues
 

class GlobalUnderstanding:
    def __init__(self, suits = VANILLA_SUITS, n_players = 2, hand_size = 5):
        self.clue_tokens = 8
        self.play_stacks = dict([(suit, 0) for suit in suits])
        self.strikes = 0
        self.max_stacks = dict([(suit, 5) for suit in suits])
        self.deck_size = len(suits) * len(SUIT_CONTENTS)
        self.unseen_copies = dict([(str(rank) + suit, SUIT_CONTENTS.count(str(rank))) for rank in range(1, 6) for suit in suits])
        self.usable_copies = deepcopy(self.unseen_copies)
        self.hand_possibilities = []
        for player in range(n_players):
            self.hand_possibilities.append([])
            for card in range(hand_size):
                self.draw(player)
        self.instructed_plays = [[] for player in range(n_players)]
        self.instructed_trash = [[] for player in range(n_players)]
        self.instructed_chop = [None for player in range(n_players)]
        self.instructed_to_lock = [False for player in range(n_players)]
        self.turns_left = None

    def draw(self, player, replacing = None):
        if replacing is not None:
            for i, slot in reversed(list(enumerate(self.instructed_plays[player]))):
                if slot < replacing:
                    self.instructed_plays[player][i] += 1
                elif slot == replacing:
                    self.instructed_plays[player].pop(i)
            for i, slot in reversed(list(enumerate(self.instructed_trash[player]))):
                if slot < replacing:
                    self.instructed_trash[player][i] += 1
                elif slot == replacing:
                    self.instructed_trash.pop(i)
            self.instructed_chop[player] = None
            self.instructed_to_lock[player] = False

            self.hand_possibilities[player].pop(replacing)
        if self.deck_size == 0:
            self.turns_left -= 1
        else:
            self.deck_size -= 1
            new_card = set([identity for identity, copies in self.unseen_copies.items() if copies > 0])
            self.hand_possibilities[player] = [new_card] + self.hand_possibilities[player]
            if self.deck_size == 0:
                self.turns_left = len(self.hand_possibilities)
        

    def reveal_copy(self, identity):
        if self.unseen_copies[identity] == 0:
            print('self.unseen_copies[identity] == 0', self, identity)
            return
        self.unseen_copies[identity] -= 1
        if self.unseen_copies[identity] == 0:
            self.last_copy_revealed(identity)


    def last_copy_revealed(self, identity):
        for player, hand in enumerate(self.hand_possibilities):
            for slot, card in enumerate(hand):
                if len(card) == 1:
                    continue
                try:
                    self.hand_possibilities[player][slot].remove(identity)
                except ValueError:
                    continue
                if len(card) == 1:
                    self.reveal_copy(next(iter(card)))

    def discard_copy(self, identity):
        assert self.usable_copies[identity] > 0
        self.usable_copies[identity] -= 1
        if self.usable_copies[identity] == 0:
            self.last_copy_discarded(identity)

    def last_copy_discarded(self, identity):
        suit, rank = parse_identity(identity)
        self.max_stacks[suit] = min(rank - 1, self.max_stacks[suit])

    def play(self, player, identity, slot):
        print('play', player, identity, slot)
        suit, rank = parse_identity(identity)

        if self.play_stacks[suit] == rank - 1:
            self.play_stacks[suit] = rank
            if rank == 5:
                self.clue_tokens += 1
        else:
            self.strikes += 1
            if self.strikes >= 3:
                # Model a strikeout as scoring the current score
                self.max_stacks = self.play_stacks
                return
        misplayed = self.play_stacks[suit] != rank

        possibilities = self.hand_possibilities[player][slot]

        self.interpret_play(player, identity, slot)

        self.draw(player, replacing = slot)
        if len(possibilities) > 1:
            self.reveal_copy(identity)
        if misplayed:
            self.discard_copy(identity)

    def interpret_play(self, player, identity, slot):
        self.instructed_chop[player] = None
        self.instructed_to_lock[player] = False

    def discard(self, player, identity, slot):
        print('discard', player, identity, slot)
        self.interpret_discard(player, identity, slot)

        self.draw(player, replacing = slot)
        self.reveal_copy(identity)
        self.discard_copy(identity)
        self.clue_tokens += 1

    def interpret_discard(self, player, identity, slot):
        self.instructed_chop[player] = None
        self.instructed_to_lock[player] = False

    def clue(self, receiver, value, touching):
        old_receiver_possibilities = deepcopy(self.hand_possibilities[receiver])

        self.apply_information(receiver, value, touching)

        # Bug?: old_receiver_possibilities doesn't account for newly revealed knowledge in giver's hand
        self.interpret_clue(receiver, old_receiver_possibilities, value, touching)

        self.clue_tokens -= 1

    def apply_information(self, receiver, value, touching):
        hand_possibilities = self.hand_possibilities[receiver]
        for slot, card_possibilities in enumerate(hand_possibilities):
            if len(card_possibilities) == 1:
                continue

            if slot in touching:
                self.hand_possibilities[receiver][slot] = filter_touched(card_possibilities, value)
            else:
                self.hand_possibilities[receiver][slot] = filter_untouched(card_possibilities, value)

            if len(card_possibilities) == 1:
                self.reveal_copy(next(iter(card_possibilities)))

    def interpret_clue(self, receiver, old_receiver_possibilities, value, touching):
        old_receiver_identified_plays = self.get_identified_plays(old_receiver_possibilities)
        old_receiver_known_trashes = self.get_known_trashes(old_receiver_possibilities)
        receiver_was_loaded = old_receiver_identified_plays or old_receiver_known_trashes or self.instructed_plays[receiver] or self.instructed_trash[receiver]

        old_receiver_unclued = get_unclued(old_receiver_possibilities)
        old_receiver_unclued = [slot for slot in old_receiver_unclued if slot not in self.instructed_plays[receiver] and slot not in self.instructed_trash[receiver]]

        receiver_identified_plays = self.get_identified_plays(self.hand_possibilities[receiver])
        receiver_known_trashes = self.get_known_trashes(self.hand_possibilities[receiver])

        new_receiver_identified_plays = [play for play in receiver_identified_plays if play not in old_receiver_identified_plays]
        new_receiver_known_trashes = [slot for slot in receiver_known_trashes if slot not in old_receiver_known_trashes]
        if new_receiver_identified_plays or new_receiver_known_trashes:
            return

        referent = get_referent(old_receiver_unclued, touching)
        if referent is None:
            return

        if value in SUIT_CONTENTS:
            if receiver_was_loaded:
                if old_receiver_unclued[0] in touching:
                    self.instructed_trash[receiver].append(referent)
                else:
                    self.instructed_plays[receiver].append(referent)
            elif not self.instructed_to_lock[receiver] and referent is old_receiver_unclued[0]:
                self.instructed_chop[receiver] = None
                self.instructed_to_lock[receiver] = True
            else:
                self.instructed_chop[receiver] = referent
                self.instructed_to_lock[receiver] = False
        else:
            self.instructed_plays[receiver].append(referent)

    def make_expected_move(self, player, hand):
        identified_plays = self.get_identified_plays(self.hand_possibilities[player])
        if identified_plays:
            slot, identity = identified_plays[0]
            self.play(player, identity, slot)
            return
        if self.instructed_plays[player]:
            slot = self.instructed_plays[player][0]
            identity = hand[slot]["name"]
            self.play(player, identity, slot)
            return
        if self.clue_tokens == 8:
            self.clue_tokens -= 1
            return
        if self.instructed_trash[player]:
            slot = self.instructed_trash[player][0]
            identity = hand[slot]["name"]
            self.discard(player, identity, slot)
            return
        known_trashes = self.get_known_trashes(self.hand_possibilities[player])
        if known_trashes:
            slot = known_trashes[0]
            identity = hand[slot]["name"]
            self.discard(player, identity, slot)
            return
        if self.instructed_chop[player] != None:
            identity = hand[self.instructed_chop[player]]["name"]
            self.discard(player, identity, self.instructed_chop[player])
            return
        if self.instructed_to_lock[player] and self.clue_tokens > 0:
            print('instructed to lock')
            self.clue_tokens -= 1
            return
        unclued = get_unclued(self.hand_possibilities[player])
        if unclued:
            chop = unclued[0]
            identity = hand[chop]["name"]
            self.discard(player, identity, chop)
            return
        self.discard(player, hand[0]["name"], 0)
            

    def get_identified_plays(self, hand_possibilities):
        return [(i, next(iter(card_possibilities))) for i, card_possibilities in enumerate(hand_possibilities) if len(card_possibilities) == 1 and is_playable(next(iter(card_possibilities)), self.play_stacks)]

    def get_known_trashes(self, hand_possibilities):
        return [i for i, card_possibilities in enumerate(hand_possibilities) if self.is_known_trash(card_possibilities)]

    def is_known_trash(self, card_possibilities):
        return all([not self.useful(identity) for identity in card_possibilities])

    def useful(self, identity):
        suit = identity[1]
        rank = int(identity[0])
        return self.play_stacks[suit] < rank and rank <= self.max_stacks[suit]

    def score(self):
        return sum(self.play_stacks.values())

    def max_score(self):
        return sum(self.max_stacks.values())

    def max_score_adjusted(self):
        pace = self.get_pace()
        if pace < 0:
            return self.max_score() + pace
        return self.max_score()

    def get_pace(self):
        draws_left = self.deck_size + (self.turns_left if self.turns_left != None else len(self.hand_possibilities))
        plays_left = self.max_score() - self.score()
        return draws_left - plays_left

def parse_identity(identity):
    return identity[1], int(identity[0])

def get_referent(old_receiver_unclued, touching):
    for i, slot in enumerate(old_receiver_unclued):
        if old_receiver_unclued[(i + 1) % len(old_receiver_unclued)] in touching:
            return slot


def get_unclued(hand_possibilities):
    return [i for i, card_possibilities in enumerate(hand_possibilities) if not is_clued(card_possibilities)]

def is_clued(card_possibilities):
    if len(card_possibilities) > 5:
        return False
    possible_ranks_per_suit = {}
    possible_suits_per_rank = {}
    for possibility in card_possibilities:
        rank = possibility[0]
        suit = possibility[1]
        try:
            possible_ranks_per_suit[suit].add(rank)
        except KeyError:
            possible_ranks_per_suit[suit] = set([rank])
        try:
            possible_suits_per_rank[rank].add(suit)
        except KeyError:
            possible_suits_per_rank[rank] = set([suit])
    return all([len(ranks) == 1 for ranks in possible_ranks_per_suit.values()]) or all([len(suits) == 1 for suits in possible_suits_per_rank.values()])

def get_touching(hand, clue_value):
    return [i for i, card in enumerate(hand) if clue_value in card["name"]]

def filter_touched(card_possibilities, clue_value):
    return [identity for identity in card_possibilities if clue_value in identity]

def filter_untouched(card_possibilities, clue_value):
    return [identity for identity in card_possibilities if clue_value not in identity]

def newest_to_oldest(cards):
    return list(reversed(sorted(cards, key = lambda card: card["time"])))
