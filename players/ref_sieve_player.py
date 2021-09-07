"""Referential Sieve Player
"""

from hanabi_classes import *
from bot_utils import is_playable, deduce_plays, is_critical as is_last_copy
from copy import deepcopy

class ReferentialSievePlayer(AIPlayer):

    @classmethod
    def get_name(cls):
        return 'ref_sieve'

    def __init__(self, *args):
        """Can be overridden to perform initialization, but must call super"""
        super(ReferentialSievePlayer, self).__init__(*args)

    def play(self, r):
        r.HandHistory.append([newest_to_oldest(deepcopy(hand.cards)) if hand.seat != r.whoseTurn else 'redacted' for hand in r.h])
        recent_actions = r.playHistory[-r.nPlayers]
        if len(recent_actions) < r.nPlayers:
            self.global_understanding = GlobalUnderstanding()
        initialActor = r.whoseTurn - len(recent_actions)
        for i, action in enumerate(recent_actions):
            actor = (initialActor + i + r.nPlayers) % r.nPlayers
            action_type, action = action
            if action_type == 'play':
                self.global_understanding.play(actor, action["name"], action["position"])
            elif action_type == 'discard':
                self.global_understanding.discard(actor, action["name"], action["position"])
            elif action_type == 'hint':
                receiver, value = action
                hands_at_time = r.HandHistory[-len(recent_actions) + i]
                touching = get_touching(hands_at_time[receiver], value)
                self.global_understanding.clue(receiver, value, touching)


        return find_best_move(r.HandHistory[-1], r.whoseTurn, self.global_understanding)


    def end_game_logging(self):
        """Can be overridden to perform logging at the end of the game"""
        pass

def find_best_move(hands, player, global_understanding):
    if global_understanding.clue_tokens > 0:
        for clue in get_possible_clues(hands, player):
            simulated_hands = deepcopy(hands)
            simulation = deepcopy(global_understanding)
            simulation.clue(*clue)
            for player_offset in range(1, len(hands)):
                actor = (player + player_offset) % len(hands)
                action_type, action = get_expected_action(player, simulation)
                old_deck_size = simulation.deck_size
                if action_type == 'play':
                    slot = action
                    simulation.play(actor, simulated_hands[actor][slot], slot)
                    simulated_hands[actor].pop(slot)
                    if old_deck_size > 0:
                        simulated_hands[actor] = [set(simulation.unseen_copies.keys())] + simulated_hands[actor]
                elif action_type == 'discard':
                    slot = action
                    simulation.discard(actor, simulated_hands[actor][slot], slot)
                    simulated_hands[actor].pop(slot)
                    if old_deck_size > 0:
                        simulated_hands[actor] = [set(simulation.unseen_copies.keys())] + simulated_hands[actor]
                else:
                    raise "todo"





def get_expected_action(player, global_understanding):




class GlobalUnderstanding:
    def __init__(self, suits = VANILLA_SUITS, n_players = 2, hand_size = 5):
        self.clue_tokens = 8
        self.play_stacks = dict([(suit, 0) for suit in suits])
        self.strikes = 0
        self.max_stacks = dict([(suit, 5) for suit in suits])
        self.deck_size = len(suits) * SUIT_CONTENTS
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
            for i, slot in reversed(enumerate(self.instructed_plays[player])):
                if slot < replacing:
                    self.instructed_plays[player][i] += 1
                elif slot == replacing:
                    self.instructed_plays.pop(i)
            for i, slot in reversed(enumerate(self.instructed_trash[player])):
                if slot < replacing:
                    self.instructed_trash[player][i] += 1
                elif slot == replacing:
                    self.instructed_trash.pop(i)
            self.instructed_chop[player] = None
            self.instructed_to_lock[player] = False

            self.hand_possibilities[player].pop(replacing)
        if self.deck_size > 0:
            self.deck_size -= 1
            new_card = set(self.unseen_copies.keys())
            self.hand_possibilities[player] = [new_card] + self.hand_possibilities[player]
            if self.deck_size == 0:
                self.turns_left = len(self.hand_possibilities)

    def reveal_copy(self, identity):
        assert self.unseen_copies[identity] > 0
        self.unseen_copies[identity] -= 1
        if self.unseen_copies[identity] == 0:
            self.last_copy_revealed(identity)


    def last_copy_revealed(self, identity):
        for hand in self.hand_possibilities:
            for card in hand:
                if len(card) == 1:
                    continue
                try:
                    card.remove(identity)
                except KeyError:
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
        suit, rank = parse_identity(identity)

        if self.play_stacks[suit] == rank - 1:
            self.play_stacks[suit] = rank
        else:
            self.strikes += 1
            if self.strikes >= 3:
                self.turns_left = 0
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
        suit, rank = parse_identity(identity)

        self.interpret_discard(player, identity, slot)

        self.draw(player, replacing = slot)
        self.reveal_copy(identity)
        self.discard_copy(identity)

    def interpret_discard(self, player, identity, slot):
        self.instructed_chop[player] = None
        self.instructed_to_lock[player] = False

    def clue(self, receiver, value, touching):
        old_receiver_possibilities = deepcopy(self.hand_possibilities[receiver])

        self.apply_information(self.hand_possibilities[receiver], value, touching)

        # Bug?: old_receiver_possibilities doesn't account for newly revealed knowledge in giver's hand
        self.interpret_clue(receiver, old_receiver_possibilities, value, touching)

        self.hints -= 1

    def apply_information(self, hand_possibilities, value, touching):
        for slot, card_possibilities in enumerate(hand_possibilities):
            if len(card_possibilities) == 1:
                continue

            if slot in touching:
                card_possibilities = filter_touched(card_possibilities, value)
            else:
                card_possibilities = filter_untouched(card_possibilities, value)

            if len(card_possibilities) == 1:
                self.reveal_copy(next(iter(card_possibilities)))

    def interpret_clue(self, receiver, old_receiver_possibilities, value, touching):
        old_receiver_identified_plays = self.get_identified_plays(old_receiver_possibilities)
        old_receiver_known_trashes = self.get_known_trashes(old_receiver_possibilities)
        receiver_was_loaded = old_receiver_identified_plays or old_receiver_known_trashes or self.instructed_plays[receiver] or self.instructed_trash[receiver]

        old_receiver_unclued = get_unclued(old_receiver_possibilities)
        old_receiver_unclued = [slot for slot in old_receiver_unclued if slot not in self.instructed_plays[receiver] and slot not in self.instructed_trash[receiver]]

        receiver_identified_plays = self.get_identified_plays(new_receiver_possibilities)
        receiver_known_trashes = self.get_known_trashes(new_receiver_possibilities)

        new_receiver_identified_plays = [slot for slot in receiver_identified_plays if slot not in old_receiver_identified_plays]
        new_receiver_known_trashes = [slot for slot in receiver_known_trashes if slot not in old_receiver_known_trashes]
        if new_receiver_identified_plays or new_receiver_known_trashes:
            return

        referent = get_referent(old_receiver_unclued, touching)
        if referent is None:
            return

        if value in SUIT_CONTENTS:
            if receiver_was_loaded:
                if old_receiver_unclued[0] in touching:
                    self.instructed_trash.append(referent)
                else:
                    self.instructed_plays.append(referent)
            elif not self.instructed_to_lock[receiver] and referent is old_receiver_unclued[0]:
                self.instructed_chop[receiver] = None
                self.instructed_to_lock[receiver] = True
            else:
                self.instructed_chop[receiver] = referent
                self.instructed_to_lock[receiver] = False
        else:
            self.instructed_plays.append(referent)

    def get_identified_plays(self, hand_possibilities):
        return [i for i, card_possibilities in enumerate(hand_possibilities) if len(hand_possibilities) == 1 and is_playable(next(iter(hand_possibilities)), self.play_stacks)]

    def get_known_trashes(self, hand_possibilities):
        return [i for i, card_possibilities in enumerate(hand_possibilities)if self.is_known_trash(card_possibilities)]

    def is_known_trash(self, card_possibilities):
        return all([not self.useful(identity) for identity in card_possibilities])

    def useful(self, identity):
        suit = identity[1]
        rank = int(identity[0])
        return self.play_stacks[suit] < rank and rank <= self.max_stacks[suit]

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
    return all([len(ranks) == 1 for ranks in possible_ranks_per_suit.values()]) or all([len(suits) == 1 for suits in possible_suitss_per_rank.values()])

def get_touching(hand, clue_value):
    return [i for i, card in enumerate(hand) if clue_value in card["name"]]

def find_sacrifice(r, hand):
    lock_hint = None
    for move_type, move in reversed(r.playHistory):
        if move_type != 'hint':
            continue
        receiver, hint = move
        if receiver != r.whoseTurn:
            continue
        lock_hint = hint
        break
    slots_previously_touched = get_slots_previously_touched(hand, lock_hint)
    previously_touched = [hand[slot] for slot in slots_previously_touched]
    if previously_touched:
        return least_critical(r, previously_touched)
    return least_critical(r, hand)

def least_critical(r, cards):
    return min(cards, key=lambda card: likelihood_critical(r, card))

def likelihood_critical(r, card):
    possible_identities = get_possible_identities(card)
    num_critical = len([identity for identity in possible_identities if is_critical(r, identity)])
    return num_critical / len(possible_identities)

def get_pace(r):
    drawsLeft = len(r.deck) + (r.gameOverTimer + 1 if r.gameOverTimer else r.nPlayers)
    playsLeft = maxScore(r) - sum(r.progress.values())
    return drawsLeft - playsLeft

def newest_to_oldest(cards):
    return list(reversed(sorted(cards, key = lambda card: card["time"])))
