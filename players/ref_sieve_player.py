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
        r.HandHistory.append(
            [newest_to_oldest(deepcopy(hand.cards)) for hand in r.h])
        recent_actions = r.playHistory[-r.nPlayers:]
        if len(recent_actions) < r.nPlayers:
            self.global_understanding = GlobalUnderstanding()
        initial_actor = r.whoseTurn - len(recent_actions)
        for i, action in enumerate(recent_actions):
            actor = (initial_actor + i + r.nPlayers) % r.nPlayers
            action_type, action = action
            if action_type == 'play':
                self.global_understanding.play(
                    actor, action["name"], action["position"] - 1)
            elif action_type == 'discard':
                self.global_understanding.discard(
                    actor, action["name"], action["position"] - 1)
            elif action_type == 'hint':
                receiver, value = action
                hands_at_time = r.HandHistory[-len(recent_actions) + i]
                touching = get_touching(hands_at_time[receiver], value)
                self.global_understanding.clue(receiver, value, touching)

        best_move = find_best_move(
            r.HandHistory[-1], r.whoseTurn, self.global_understanding)
        # print('best_move', best_move, [card["name"] for card in r.HandHistory[-1][1]])
        return best_move

    def end_game_logging(self):
        """Can be overridden to perform logging at the end of the game"""
        pass


def find_best_move(hands, player, global_understanding):
    partner = (player + 1) % 2
    simulation = deepcopy(global_understanding)
    simulated_hand = deepcopy(hands[partner])
    simulation.make_expected_move(partner, simulated_hand)
    baseline_max_score = simulation.max_score_adjusted(
        player, player, simulated_hand)
    baseline_strikes = simulation.strikes
    baseline_bdrs = sum([global_understanding.usable_copies[identity] - copies for identity,
                         copies in simulation.usable_copies.items() if simulation.useful(identity)])
    baseline_locked = simulation.instructed_to_lock[partner]

    def evaluate_play(slot, good_touch_possibilities):
        if len(good_touch_possibilities) == 1:
            identity = next(iter(good_touch_possibilities))
            simulation = deepcopy(global_understanding)
            simulated_hand = deepcopy(hands[partner])
            simulation.play(player, identity, slot)
            simulation.make_expected_move(partner, simulated_hand)
            score = simulation.max_score_adjusted(
                player, player, simulated_hand)
            locked = simulation.instructed_to_lock[partner]
            bdrs = sum([global_understanding.usable_copies[identity] - copies for identity,
                        copies in simulation.usable_copies.items() if simulation.useful(identity)])
            print('simulated play', score, -
                  simulation.strikes, not locked, -bdrs, slot)
            return score, -simulation.strikes, not locked, -bdrs, -slot
        else:
            return baseline_max_score, -baseline_strikes, not baseline_locked, -baseline_bdrs, -slot

    best_play_slot = None
    best_play_score = 0
    best_play_negated_strikes = -3
    best_play_unlocked = False
    best_play_negated_bdrs = -100

    plays = [evaluate_play(slot, good_touch_possibilities)
             for slot, good_touch_possibilities in global_understanding.get_good_touch_plays_for_player(player)]
    if plays:
        best_play_score, best_play_negated_strikes, best_play_unlocked, best_play_negated_bdrs, best_play_negated_slot = max(
            plays)
        best_play_slot = -best_play_negated_slot

    if best_play_slot == None and global_understanding.instructed_plays[player]:
        best_play_slot = global_understanding.instructed_plays[player][0]
        best_play_score = baseline_max_score
        best_play_negated_strikes = -simulation.strikes
        best_play_unlocked = not baseline_locked
        best_play_negated_bdrs = -baseline_bdrs

    # print('best_play', best_play_slot, best_play_score,
    #       best_play_negated_strikes, best_play_negated_bdrs, best_play_unlocked)

    def evaluate_clue(clue_value, touching):
        simulation = deepcopy(global_understanding)
        simulated_hand = deepcopy(hands[partner])
        simulation.clue(partner, clue_value, touching)
        simulation.make_expected_move(partner, simulated_hand)

        score = simulation.max_score_adjusted(player, player, simulated_hand)
        tempo = simulation.score() + len(simulation.instructed_plays[partner]) + len(
            simulation.get_good_touch_plays_for_player(partner))
        bdrs = sum([global_understanding.usable_copies[identity] - copies for identity,
                    copies in simulation.usable_copies.items() if simulation.useful(identity)])
        locked = simulation.instructed_to_lock[partner]
        simulated_current_score = simulation.score()
        simulation.make_expected_move(partner, simulated_hand)
        while simulation.score() > simulated_current_score:
            simulated_current_score = simulation.score()
            simulation.make_expected_move(partner, simulated_hand)
        strikes = simulation.strikes
        print('simulated clue', score, -simulation.strikes,
              tempo, not locked, -bdrs, clue_value)
        return score, -strikes, tempo, not locked, -bdrs, clue_value

    best_clue = None
    best_clue_score = 0
    best_clue_negated_strikes = -3
    best_clue_tempo = 0
    best_clue_negated_bdrs = -100
    best_clue_unlocked = False
    if global_understanding.clue_tokens >= 1:
        clues = [evaluate_clue(clue_value, touching)
                 for clue_value, touching in get_possible_clues(hands[partner])]
        if clues:
            best_clue_score, best_clue_negated_strikes, best_clue_tempo, best_clue_unlocked, best_clue_negated_bdrs, best_clue = max(
                clues)
    print('best_clue', best_clue, best_clue_score, best_clue_negated_strikes,
          best_clue_tempo, best_clue_negated_bdrs, best_clue_unlocked)

    best_discard = None
    discard_score = 0
    discard_strikes = 3
    if global_understanding.clue_tokens < 8:
        avoid_discarding = False
        if global_understanding.instructed_trash[player]:
            best_discard = global_understanding.instructed_trash[player][0]
        else:
            known_trashes = global_understanding.get_known_trashes(
                global_understanding.hand_possibilities[player])
            if known_trashes:
                best_discard = known_trashes[0]
            elif global_understanding.instructed_chop[player] != None:
                best_discard = global_understanding.instructed_chop[player]
            else:
                if global_understanding.instructed_to_lock[player] or best_play_slot != None:
                    avoid_discarding = True
                unclued = get_unclued(
                    global_understanding.hand_possibilities[player])
                if unclued:
                    best_discard = unclued[0]
                else:
                    best_discard = 0

        simulation = deepcopy(global_understanding)
        simulated_hand = deepcopy(hands[partner])
        trash_identities = [
            identity
            for identity in simulation.hand_possibilities[player][best_discard]
            if not simulation.useful(identity)]
        discard_identity = min(trash_identities) if trash_identities else min(
            simulation.hand_possibilities[player][best_discard])
        simulation.discard(player, discard_identity, best_discard)
        simulation.make_expected_move(partner, simulated_hand)
        discard_score = 0 if avoid_discarding else simulation.max_score_adjusted(
            player, player, simulated_hand)
        discard_strikes = simulation.strikes
    print('best_discard', best_discard, discard_score)

    maximum = max(
        (best_play_score,
         best_play_negated_strikes,
         best_play_unlocked,
         global_understanding.clue_tokens >= 4 and best_play_negated_bdrs,
         'play'),
        (best_clue_score,
         best_clue_negated_strikes,
         best_clue_unlocked,
         global_understanding.clue_tokens >= 4 and best_clue_negated_bdrs,
         'clue'),
        (discard_score,
         -discard_strikes,
         not baseline_locked,
         global_understanding.clue_tokens >= 4 and -baseline_bdrs,
         'discard'))
    # print('maximum', maximum)
    _, _, _, _, move = maximum
    if move == 'play':
        return 'play', hands[player][best_play_slot]
    if move == 'discard':
        return 'discard', hands[player][best_discard]
    if move == 'clue':
        return 'hint', (partner, best_clue)


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
    def __init__(self, suits=VANILLA_SUITS, n_players=2, hand_size=5):
        self.clue_tokens = 8
        self.play_stacks = dict([(suit, 0) for suit in suits])
        self.strikes = 0
        self.max_stacks = dict([(suit, 5) for suit in suits])
        self.deck_size = len(suits) * len(SUIT_CONTENTS)
        self.initial_copies = dict(
            [(str(rank) + suit, SUIT_CONTENTS.count(str(rank))) for rank in range(1, 6) for suit in suits])
        self.unseen_copies = deepcopy(self.initial_copies)
        self.usable_copies = deepcopy(self.initial_copies)
        self.hand_possibilities = []
        self.touched = []
        for player in range(n_players):
            self.hand_possibilities.append([])
            self.touched.append([])
            for card in range(hand_size):
                self.draw(player)
        self.instructed_plays = [[] for player in range(n_players)]
        self.instructed_trash = [[] for player in range(n_players)]
        self.instructed_chop = [None for player in range(n_players)]
        self.instructed_to_lock = [False for player in range(n_players)]
        self.turns_left = None

    def draw(self, player, replacing=None):
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
            self.touched[player].pop(replacing)
        if self.deck_size == 0:
            for i in range(len(self.instructed_plays[player])):
                self.instructed_plays[player][i] -= 1
            for i in range(len(self.instructed_trash[player])):
                self.instructed_trash[player][i] -= 1
        else:
            self.deck_size -= 1
            new_card_possibilities = set(
                [identity for identity, copies in self.unseen_copies.items() if copies > 0])
            self.hand_possibilities[player] = [
                new_card_possibilities] + self.hand_possibilities[player]
            self.touched[player] = [False] + self.touched[player]
            if self.deck_size == 0:
                self.turns_left = len(self.hand_possibilities)

    def reveal_copy(self, identity):
        if self.unseen_copies[identity] == 0:
            # print('self.unseen_copies[identity] == 0', self, identity)
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
            # print('self.usable_copies[identity] == 0', self, identity)
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

        if self.turns_left != None:
            self.turns_left -= 1

        self.interpret_play(player, identity, slot)

        self.draw(player, replacing=slot)
        if len(possibilities) > 1:
            self.reveal_copy(identity)
        if misplayed:
            self.discard_copy(identity)

    def interpret_play(self, player, identity, slot):
        self.instructed_chop[player] = None
        self.instructed_to_lock[player] = False

    def discard(self, player, identity, slot):
        # print('discard', player, identity, slot)

        if self.turns_left != None:
            self.turns_left -= 1

        self.interpret_discard(player, identity, slot)

        self.draw(player, replacing=slot)
        self.reveal_copy(identity)
        self.discard_copy(identity)
        self.clue_tokens += 1

    def interpret_discard(self, player, identity, slot):
        self.instructed_chop[player] = None
        self.instructed_to_lock[player] = False

    def clue(self, receiver, value, touching):
        old_receiver_possibilities = deepcopy(
            self.hand_possibilities[receiver])
        old_receiver_touched = deepcopy(self.touched[receiver])

        self.apply_information(receiver, value, touching)

        if self.turns_left != None:
            self.turns_left -= 1

        # Bug?: old_receiver_possibilities doesn't account for newly revealed knowledge in giver's hand
        self.interpret_clue(receiver, old_receiver_possibilities,
                            old_receiver_touched, value, touching)

        self.clue_tokens -= 1

    def apply_information(self, receiver, value, touching):
        hand_possibilities = self.hand_possibilities[receiver]
        for slot, card_possibilities in enumerate(hand_possibilities):
            if len(card_possibilities) == 1:
                continue

            if slot in touching:
                self.hand_possibilities[receiver][slot] = filter_touched(
                    card_possibilities, value)
                self.touched[receiver][slot] = True
            else:
                self.hand_possibilities[receiver][slot] = filter_untouched(
                    card_possibilities, value)

            if len(card_possibilities) == 1:
                self.reveal_copy(next(iter(card_possibilities)))

    def interpret_clue(self, receiver, old_receiver_possibilities, old_receiver_touched, value, touching):
        old_receiver_identified_plays = self.get_good_touch_plays(
            old_receiver_possibilities, old_receiver_touched)
        old_receiver_known_trashes = self.get_known_trashes(
            old_receiver_possibilities)
        receiver_was_loaded = old_receiver_identified_plays or\
            old_receiver_known_trashes or\
            self.instructed_plays[receiver] or\
            self.instructed_trash[receiver]

        old_receiver_unclued = get_unclued(old_receiver_possibilities)
        old_receiver_unclued = [
            slot
            for slot in old_receiver_unclued
            if slot not in self.instructed_plays[receiver]
            and slot not in self.instructed_trash[receiver]]

        receiver_identified_plays = self.get_good_touch_plays_for_player(
            receiver)
        receiver_known_trashes = self.get_known_trashes(
            self.hand_possibilities[receiver])

        new_receiver_identified_plays = [
            play
            for play, card_possibilities in receiver_identified_plays
            if play not in old_receiver_identified_plays
            and play not in old_receiver_unclued]
        new_receiver_known_trashes = [
            slot
            for slot in receiver_known_trashes
            if slot not in old_receiver_known_trashes
            and slot not in old_receiver_unclued]
        if new_receiver_identified_plays or new_receiver_known_trashes:
            return

        referent = get_referent(old_receiver_unclued, touching)
        if referent is None:
            return

        all_trash = all(
            [slot in receiver_known_trashes for slot in touching if slot in old_receiver_unclued])
        # print('all_trash', all_trash)

        if value in SUIT_CONTENTS and not all_trash:
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
        unseen_trashes = [
            identity for identity in self.unseen_copies.keys() if not self.useful(identity)]
        placeholder_card = {
            "name": unseen_trashes[0] if unseen_trashes else '1r'}
        good_touch_plays = self.get_good_touch_plays_for_player(player)
        if good_touch_plays:
            slot, good_touch_identities = good_touch_plays[0]
            identity = hand.pop(slot)["name"]
            if self.deck_size >= 1:
                hand.insert(0, placeholder_card)
            self.play(player, identity, slot)
            return
        if self.instructed_plays[player]:
            slot = self.instructed_plays[player][0]
            identity = hand.pop(slot)["name"]
            if self.deck_size >= 1:
                hand.insert(0, placeholder_card)
            self.play(player, identity, slot)
            return
        if self.clue_tokens == 8:
            self.clue_tokens -= 1
            return
        if self.clue_tokens >= 1 and self.get_pace_adjusted(player, (player + 1) % 2, hand) <= 0:
            self.clue_tokens -= 1
            return
        if self.instructed_trash[player]:
            slot = self.instructed_trash[player][0]
            identity = hand.pop(slot)["name"]
            if self.deck_size >= 1:
                hand.insert(0, placeholder_card)
            self.discard(player, identity, slot)
            return
        known_trashes = self.get_known_trashes(self.hand_possibilities[player])
        if known_trashes:
            slot = known_trashes[0]
            identity = hand.pop(slot)["name"]
            if self.deck_size >= 1:
                hand.insert(0, placeholder_card)
            self.discard(player, identity, slot)
            return
        if self.instructed_chop[player] != None:
            identity = hand.pop(self.instructed_chop[player])["name"]
            if self.deck_size >= 1:
                hand.insert(0, placeholder_card)
            self.discard(player, identity, self.instructed_chop[player])
            return
        if self.instructed_to_lock[player] and self.clue_tokens > 0:
            # print('instructed to lock')
            self.clue_tokens -= 1
            return
        unclued = get_unclued(self.hand_possibilities[player])
        if unclued:
            slot = unclued[0]
            identity = hand.pop(slot)["name"]
            if self.deck_size >= 1:
                hand.insert(0, placeholder_card)
            self.discard(player, identity, slot)
            return
        identity = hand.pop(0)["name"]
        if self.deck_size >= 1:
            hand.insert(0, placeholder_card)
        self.discard(player, identity, 0)

    def get_good_touch_plays(self, hand_possibilities, touched):
        return [
            (slot,
             [identity for identity in card_possibilities if not touched[slot]
              or self.useful(identity)]
             )
            for slot, card_possibilities in enumerate(hand_possibilities)
            if any([
                not touched[slot] or self.useful(identity)
                for identity in card_possibilities])
            and all([
                is_playable(identity, self.play_stacks)
                for identity in card_possibilities
                if not touched[slot] or self.useful(identity)])]

    def get_good_touch_plays_for_player(self, player):
        return self.get_good_touch_plays(self.hand_possibilities[player], self.touched[player])

    def get_known_trashes(self, hand_possibilities):
        return [slot for slot, card_possibilities in enumerate(hand_possibilities) if self.is_known_trash(hand_possibilities, slot)]

    def is_known_trash(self, hand_possibilities, slot):
        def duplicated(identity):
            for slot2, card_possibilities in enumerate(hand_possibilities):
                if slot2 == slot:
                    continue
                if len(card_possibilities) == 1 and next(iter(card_possibilities)) == identity:
                    return True
            return False
        return all([not self.useful(identity) or duplicated(identity) for identity in hand_possibilities[slot]])

    def useful(self, identity):
        suit, rank = parse_identity(identity)
        return self.play_stacks[suit] < rank and rank <= self.max_stacks[suit]

    def score(self):
        return sum(self.play_stacks.values())

    def max_score(self):
        return sum(self.max_stacks.values())

    def max_score_adjusted(self, current_player, player, partner_hand):
        if self.turns_left == 0:
            return self.score()
        pace = self.get_pace_adjusted(current_player, player, partner_hand)
        if pace < 0:
            return self.max_score() + pace
        return self.max_score()

    def holds_final_round_card(self, player):
        return any([
            any([
                self.useful(identity)
                for identity in card_possibilities])
            and all([
                    self.is_final_round_card(identity)
                    for identity in card_possibilities
                    if not self.touched[player][slot] or self.useful(identity)])
            for slot, card_possibilities in enumerate(self.hand_possibilities[player])])

    def is_final_round_card(self, identity):
        suit, rank = parse_identity(identity)
        return self.useful(identity) and rank >= self.max_stacks[suit] - 1

    def get_pace(self):
        draws_left = self.deck_size + \
            (self.turns_left if self.turns_left !=
             None else len(self.hand_possibilities))
        plays_left = self.max_score() - self.score()
        print('get_pace', draws_left, plays_left,
              self.deck_size, self.turns_left)
        return draws_left - plays_left

    def get_pace_adjusted(self, current_player, player, partner_hand):
        i_hold_final_round_card = self.holds_final_round_card(player)
        partner_holds_final_round_card = any(
            [self.is_final_round_card(card["name"]) for card in partner_hand])
        if self.turns_left == 1:
            if player == current_player:
                partner_holds_final_round_card = False
            else:
                i_hold_final_round_card = False
        dead_final_round_turns = sum([
            0 if holds_final_round_card else 1
            for holds_final_round_card in (i_hold_final_round_card, partner_holds_final_round_card)])
        print('dead_final_round_turns', dead_final_round_turns)

        return self.get_pace() - dead_final_round_turns


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
    return \
        all([
            len(ranks) == 1
            for ranks in possible_ranks_per_suit.values()])\
        or all([
            len(suits) == 1
            for suits in possible_suits_per_rank.values()])


def get_touching(hand, clue_value):
    return [i for i, card in enumerate(hand) if clue_value in card["name"]]


def filter_touched(card_possibilities, clue_value):
    return [identity for identity in card_possibilities if clue_value in identity]


def filter_untouched(card_possibilities, clue_value):
    return [identity for identity in card_possibilities if clue_value not in identity]


def newest_to_oldest(cards):
    return list(reversed(sorted(cards, key=lambda card: card["time"])))
