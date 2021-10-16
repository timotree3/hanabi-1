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

def find_best_move(hands, player, global_understanding):
    partner = (player + 1) % 2
    current_max_score = global_understanding.max_score_adjusted(player)
    simulation = deepcopy(global_understanding)
    simulation.make_expected_move(partner, hands[partner])
    baseline_max_score = simulation.max_score_adjusted(player)
    baseline_bdrs = sum([global_understanding.usable_copies[identity] - copies for identity, copies in simulation.usable_copies.items() if simulation.useful(identity)])
    baseline_locked = simulation.instructed_to_lock[partner]

    my_identified_plays = global_understanding.get_identified_plays(global_understanding.hand_possibilities[player])
    best_play_slot = None
    best_play_score = 0
    best_play_locked = True
    best_play_bdrs = 100
    for slot, identity in my_identified_plays:
        simulation = deepcopy(global_understanding)
        simulation.play(player, identity, slot)
        simulation.make_expected_move(partner, hands[partner])
        score = simulation.max_score_adjusted(player)
        locked = simulation.instructed_to_lock[partner]
        bdrs = sum([global_understanding.usable_copies[identity] - copies for identity, copies in simulation.usable_copies.items() if simulation.useful(identity)])
        if score < best_play_score:
            continue
        if score == best_play_score:
            if locked and not best_play_locked:
                continue
            if locked == best_play_locked and bdrs >= best_play_bdrs:
                continue
        best_play_slot = slot
        best_play_score = score
        best_play_locked = locked
        best_play_bdrs = bdrs
    
    if best_play_slot == None and global_understanding.instructed_plays[player]:
        print('including instructed play')
        best_play_slot = global_understanding.instructed_plays[player][0]
        best_play_score = baseline_max_score
        best_play_locked = baseline_locked
        best_play_bdrs = baseline_bdrs

    print('best_play', best_play_slot, best_play_score, best_play_locked, best_play_bdrs)

    best_clue = None
    best_clue_score = 0
    best_clue_strikes = 3
    best_clue_tempo = 0
    best_clue_bdrs = 100
    best_clue_locked = True
    if global_understanding.clue_tokens >= 1:
        for clue_value, touching in get_possible_clues(hands[partner]):
            simulation = deepcopy(global_understanding)
            simulation.clue(partner, clue_value, touching)
            simulation.make_expected_move(partner, hands[partner])
            score = simulation.max_score_adjusted(player)
            tempo = simulation.score() + len(simulation.instructed_plays[partner]) + len(simulation.get_identified_plays(simulation.hand_possibilities[partner]))
            bdrs = sum([global_understanding.usable_copies[identity] - copies for identity, copies in simulation.usable_copies.items() if simulation.useful(identity)])
            locked = simulation.instructed_to_lock[partner]
            while simulation.turns_left != 0 and simulation.instructed_plays[partner] or simulation.get_identified_plays(simulation.hand_possibilities[partner]):
                simulation.make_expected_move(partner, hands[partner])
            strikes = simulation.strikes
            print('simulated', clue_value, score, strikes, tempo, bdrs, locked)
            if score < best_clue_score:
                continue
            if score == best_clue_score:
                if strikes > best_clue_strikes:
                    continue
                if strikes == best_clue_strikes:
                    if tempo < best_clue_tempo:
                        continue
                    if tempo == best_clue_tempo:
                        if locked and not best_clue_locked:
                            continue
                        if locked == best_clue_locked and bdrs >= best_clue_bdrs:
                            continue
            
            best_clue = clue_value
            best_clue_score = score
            best_clue_strikes = strikes
            best_clue_tempo = tempo
            best_clue_bdrs = bdrs
            best_clue_locked = locked
    print('best_clue', best_clue)


    if best_play_slot != None:
        if best_clue_score >= best_play_score and best_play_locked and not best_clue_locked:
            print('best_play_locked', best_play_locked)
            return 'hint', (partner, best_clue)
    else:
        if best_clue_score >= baseline_max_score and baseline_locked and not best_clue_locked:
            return 'hint', (partner, best_clue)


    if best_play_score == current_max_score:
        return 'play', hands[player][best_play_slot]

    if global_understanding.clue_tokens == 8:
        if best_clue_score > best_play_score:
            return 'hint', (partner, best_clue)
        else:
            return 'play', hands[player][best_play_slot]
        
    if global_understanding.clue_tokens >= 4 and (best_clue_score > baseline_max_score or (best_clue_score == baseline_max_score and best_clue_bdrs < baseline_bdrs)):
        return 'hint', (partner, best_clue)

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

    simulation = deepcopy(global_understanding)
    trash_identities = [identity for identity in simulation.hand_possibilities[player][best_discard] if not simulation.useful(identity)]
    discard_identity = min(trash_identities) if trash_identities else min(simulation.hand_possibilities[player][best_discard])
    simulation.discard(player, discard_identity, best_discard)
    simulation.make_expected_move(partner, hands[partner])
    discard_score = simulation.max_score_adjusted(player)
    print('best_discard', best_discard, discard_score)

    if best_clue != None and best_clue_score > discard_score:
        return 'hint', (partner, best_clue)

    if best_play_slot != None and best_play_score >= discard_score:
        return 'play', hands[player][best_play_slot]

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
        self.initial_copies = dict([(str(rank) + suit, SUIT_CONTENTS.count(str(rank))) for rank in range(1, 6) for suit in suits])
        self.unseen_copies = deepcopy(self.initial_copies)
        self.usable_copies = deepcopy(self.initial_copies)
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
                    self.instructed_trash[player].pop(i)
            self.instructed_chop[player] = None
            self.instructed_to_lock[player] = False

            self.hand_possibilities[player].pop(replacing)
        if self.deck_size == 0:
            for i in range(len(self.instructed_plays[player])):
                self.instructed_plays[player][i] -= 1
            for i in range(len(self.instructed_trash[player])):
                self.instructed_trash[player][i] -= 1
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
        if self.usable_copies[identity] == 0:
            print('self.usable_copies[identity] == 0', self, identity)
            return
        self.usable_copies[identity] -= 1
        if self.usable_copies[identity] == 0:
            self.last_copy_discarded(identity)

    def last_copy_discarded(self, identity):
        if not self.useful(identity):
            return
        suit, rank = parse_identity(identity)
        self.max_stacks[suit] = min(rank - 1, self.max_stacks[suit])

    def play(self, player, identity, slot):
        # print('play', player, identity, slot)
        suit, rank = parse_identity(identity)

        if self.play_stacks[suit] == rank - 1:
            self.play_stacks[suit] = rank
            if rank == 5 and self.clue_tokens != 8:
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
        if self.turns_left == 0:
            return
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
        suit, rank = parse_identity(identity)
        return self.play_stacks[suit] < rank and rank <= self.max_stacks[suit]

    def score(self):
        return sum(self.play_stacks.values())

    def max_score(self):
        return sum(self.max_stacks.values())

    def max_score_adjusted(self, current_player):
        pace = self.get_pace()
        dead_final_round_turns = sum([0 if self.holds_final_round_card(player) else 1 for player in range(len(self.hand_possibilities)) if self.turns_left == None or self.turns_left == 1 and player == current_player or self.turns_left == 2])
        pace -= dead_final_round_turns
        if pace < 0:
            return self.max_score() + pace
        return self.max_score()

    def holds_final_round_card(self, player):
        return any([all([self.is_final_round_card(identity) for identity in card_possibilities]) for card_possibilities in self.hand_possibilities[player]])

    def is_final_round_card(self, identity):
        suit, rank = parse_identity(identity)
        return self.useful(identity) and rank >= self.max_stacks[suit] - 1

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
