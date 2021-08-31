"""Referential Sieve Player
"""

from hanabi_classes import *
from bot_utils import is_playable, deduce_plays, is_critical

class ReferentialSievePlayer(AIPlayer):

    @classmethod
    def get_name(cls):
        return 'ref_sieve'

    def __init__(self, *args):
        """Can be overridden to perform initialization, but must call super"""
        self.my_instructed_plays = []
        self.partner_instructed_plays = []
        self.my_instructed_discard = None
        self.partner_instructed_discard = None
        super(ReferentialSievePlayer, self).__init__(*args)

    def play(self, r):
        my_hand = newest_to_oldest(r.h[r.whoseTurn].cards)
        partner_idx = (r.whoseTurn + 1) % r.nPlayers
        partner_hand = newest_to_oldest(r.h[partner_idx].cards)
        self.my_instructed_plays = [play for play in self.my_instructed_plays if play in my_hand]
        self.partner_instructed_plays = [play for play in self.partner_instructed_plays if play in partner_hand]
        if self.my_instructed_discard not in my_hand or my_hand[0]["time"] > self.my_instructed_discard["time"]:
            self.my_instructed_discard = None
        if self.partner_instructed_discard not in partner_hand or partner_hand[0]["time"] > self.partner_instructed_discard["time"]:
            self.partner_instructed_discard = None
        identified_plays = deduce_plays(my_hand, r.progress, r.suits)
        partner_identified_plays = deduce_plays(partner_hand, r.progress, r.suits)
        play = self.get_instructed_play(r)
        was_tempo = self.was_tempo(r, identified_plays)
        trashes = get_known_trash(r, my_hand)
        was_fix = self.was_fix(r, trashes)
        if play and not was_tempo and not was_fix:
            self.my_instructed_plays.append(play)
        discard = self.get_instructed_discard(r)
        if discard and not was_tempo and not was_fix:
            self.my_instructed_discard = discard
        partner_loaded = self.partner_instructed_plays != [] or partner_identified_plays != []
        pace = get_pace(r)
        my_chop = self.my_instructed_discard if self.my_instructed_discard else my_hand[0]
        partner_chop = self.partner_instructed_discard if self.partner_instructed_discard else partner_hand[0]
        partner_chop_useful = useful(r, partner_chop["name"])
        partner_shouldnt_discard = not partner_loaded and (pace <= 0 or partner_chop_useful)
        if r.hints > 0 and partner_shouldnt_discard:
            hint = self.find_hint(r)
            if hint:
                return 'hint', hint
            tempo = find_tempo(r)
            if tempo:
                return 'hint', tempo
            fix = find_fix(r)
            if fix and partner_chop_useful:
                return 'hint', fix
        if r.hints > 0 and not partner_loaded:
            save = self.find_save(r, partner_chop)
            if save:
                return 'hint', save
        if self.my_instructed_plays:
            return 'play', self.my_instructed_plays.pop(0)
        if identified_plays:
            return 'play', identified_plays[0]
        if r.hints >= 7 or (r.hints > 0 and pace <= 2):
            hint = self.find_hint(r)
            if hint:
                return 'hint', hint
            tempo = find_tempo(r)
            if tempo:
                return 'hint', tempo
        if r.hints == 8 or (r.hints > 0 and partner_loaded and pace <= 1):
            return 'hint', self.find_stall(r, partner_chop)
        if trashes:
            return 'discard', trashes[0]
        return 'discard', my_chop

    def find_hint(self, r):
        partner_idx = (r.whoseTurn + 1) % r.nPlayers
        partner_hand = newest_to_oldest(r.h[partner_idx].cards)
        for card in partner_hand:
            hypothetical_color = card["name"][1]
            if hypothetically_tempo(partner_hand, hypothetical_color, self.partner_instructed_plays, r.progress):
                continue
            slots_touched = get_slots_hypothetically_touched(partner_hand, hypothetical_color)
            slots_newly_touched = [slot for slot in slots_touched if not currently_touched(partner_hand[slot]) and partner_hand[slot] not in self.partner_instructed_plays]
            if len(slots_newly_touched) == 0:
                continue
            focus = get_focus(slots_newly_touched)
            slots_currently_touched = get_slots_currently_touched(partner_hand) + [partner_hand.index(play) for play in self.partner_instructed_plays]
            referenced_card = get_referenced_card(partner_hand, focus, slots_currently_touched)
            if is_playable(referenced_card, r.progress):
                self.partner_instructed_plays.append(referenced_card)
                return partner_idx, hypothetical_color
        return None

    def was_tempo(self, r, identified_plays):
        if len(r.playHistory) == 0:
            return False

        most_recent_move_type, most_recent_move = r.playHistory[-1]
        if most_recent_move_type != 'hint':
            return False
        _who, most_recent_hint = most_recent_move
        for play in identified_plays:
            if len(play["direct"]) >= 2 and play["direct"][-1] == most_recent_hint and most_recent_hint not in play["direct"][:-1] and play not in self.my_instructed_plays:
                return True
        return False

    def was_fix(self, r, trashes):
        if len(r.playHistory) == 0:
            return False

        most_recent_move_type, most_recent_move = r.playHistory[-1]
        if most_recent_move_type != 'hint':
            return False
        _who, most_recent_hint = most_recent_move
        for trash in trashes:
            if len(trash["direct"]) >= 2 and trash["direct"][-1] == most_recent_hint and most_recent_hint not in trash["direct"][:-1]:
                return True
        return False


    def get_instructed_play(self, r):
        if len(r.playHistory) == 0:
            return None
        my_hand = newest_to_oldest(r.h[r.whoseTurn].cards)

        most_recent_move_type, most_recent_move = r.playHistory[-1]
        if most_recent_move_type != 'hint':
            return None
        _who, most_recent_hint = most_recent_move
        if most_recent_hint in SUIT_CONTENTS:
            return None
        slots_touched = get_slots_touched(my_hand, most_recent_hint)
        slots_newly_touched = [slot for slot in slots_touched if not previously_touched(my_hand[slot], most_recent_hint) and my_hand[slot] not in self.my_instructed_plays]
        if len(slots_newly_touched) == 0:
            return None
        focus = get_focus(slots_newly_touched)
        slots_previously_touched = get_slots_previously_touched(my_hand, most_recent_hint) + [my_hand.index(play) for play in self.my_instructed_plays]
        return get_referenced_card(my_hand, focus, slots_previously_touched)

    def get_instructed_discard(self, r):
        if len(r.playHistory) == 0:
            return None
        my_hand = newest_to_oldest(r.h[r.whoseTurn].cards)

        most_recent_move_type, most_recent_move = r.playHistory[-1]
        if most_recent_move_type != 'hint':
            return None
        _who, most_recent_hint = most_recent_move
        if most_recent_hint in VANILLA_SUITS:
            return None
        slots_touched = get_slots_touched(my_hand, most_recent_hint)
        slots_newly_touched = [slot for slot in slots_touched if not previously_touched(my_hand[slot], most_recent_hint) and my_hand[slot] not in self.my_instructed_plays]
        if len(slots_newly_touched) == 0:
            return None
        focus = get_focus(slots_newly_touched)
        slots_previously_touched = get_slots_previously_touched(my_hand, most_recent_hint) + [my_hand.index(play) for play in self.my_instructed_plays]
        return get_referenced_card(my_hand, focus, slots_previously_touched)


    def find_save(self, r, partner_chop, stalling = False):
        partner_idx = (r.whoseTurn + 1) % r.nPlayers
        partner_hand = newest_to_oldest(r.h[partner_idx].cards)
        if not stalling and not is_critical(partner_chop["name"], r):
            return None
        unclued = get_unclued(partner_hand, self.partner_instructed_plays)
        for card in unclued:
            hypothetical_rank = card["name"][0]
            slots_touched = get_slots_hypothetically_touched(partner_hand, hypothetical_rank)
            slots_newly_touched = [slot for slot in slots_touched if partner_hand[slot] in unclued]
            focus = get_focus(slots_newly_touched)
            slots_currently_touched = get_slots_currently_touched(partner_hand) + [partner_hand.index(play) for play in self.partner_instructed_plays]
            referenced_card = get_referenced_card(partner_hand, focus, slots_currently_touched)
            if not is_critical(referenced_card["name"], r):
                self.partner_instructed_discard = referenced_card
                return partner_idx, hypothetical_rank

    def find_stall(self, r, partner_chop):
        save = self.find_save(r, partner_chop, stalling=True)
        if save:
            return save
        partner_idx = (r.whoseTurn + 1) % r.nPlayers
        partner_hand = newest_to_oldest(r.h[partner_idx].cards)
        clued = get_slots_currently_touched(partner_hand) + [partner_hand.index(play) for play in self.partner_instructed_plays]
        for clued_slot in clued:
            card = partner_hand[clued_slot]
            hypothetical_rank = card["name"][0]
            slots_touched = get_slots_hypothetically_touched(partner_hand, hypothetical_rank)
            slots_newly_touched = [slot for slot in slots_touched if partner_hand[slot] not in clued]
            if len(slots_newly_touched) == 0:
                return partner_idx, hypothetical_rank
            hypothetical_color = card["name"][1]
            slots_touched = get_slots_hypothetically_touched(partner_hand, hypothetical_color)
            slots_newly_touched = [slot for slot in slots_touched if partner_hand[slot] not in clued]
            if len(slots_newly_touched) == 0:
                return partner_idx, hypothetical_color
        # Fall back to random clue
        return partner_idx, partner_hand[0]["name"][0]


    def end_game_logging(self):
        """Can be overridden to perform logging at the end of the game"""
        pass

def get_unclued(hand, instructed_plays):
    return [card for card in hand if card["direct"] == [] and card not in instructed_plays]

def get_known_trash(r, hand):
    return [card for card in hand if is_known_trash(r, card)]

def is_known_trash(r, card):
    return all([not useful(r, identity) for identity in get_possible_identities(card)])

def get_possible_identities(card):
    possible_suits = set(VANILLA_SUITS)
    possible_ranks = set(SUIT_CONTENTS)
    for positive in card["direct"]:
        if positive in SUIT_CONTENTS:
            possible_ranks = set([positive])
        else:
            possible_suits = set([positive])
    for negative in card["indirect"]:
        try:
            if negative in SUIT_CONTENTS:
                    possible_ranks.remove(negative)
            else:
                possible_suits.remove(negative)
        except KeyError:
            pass
    return [rank + suit for rank in possible_ranks for suit in possible_suits]

def hypothetically_tempo(hand, hint, instructed_plays, progress):
    for card in hand:
        if card in instructed_plays:
            continue
        if not is_playable(card, progress):
            continue
        if hint in card["direct"]:
            continue
        if hint in SUIT_CONTENTS:
            if hint == card["name"][1] and card["name"][0] in card["direct"]:
                return True
        else:
            if hint == card["name"][0] and card["name"][1] in card["direct"]:
                return True
    return False


def get_pace(r):
    drawsLeft = len(r.deck) + (r.gameOverTimer + 1 if r.gameOverTimer else r.nPlayers)
    playsLeft = maxScore(r) - sum(r.progress.values())
    return drawsLeft - playsLeft

def maxScore(r):
    return sum(maxStacks(r).values())

def maxStacks(r):
    maxDiscards = [3, 2, 2, 2, 1]
    discards = dict([(suit, [0 for i in range(5)]) for suit in VANILLA_SUITS])
    maxScore = dict([(suit, 5) for suit in VANILLA_SUITS])
    for card in r.discardpile:
        suit = card[1]
        rank = int(card[0]) - 1
        if r.progress[suit] > rank:
            continue
        discards[suit][rank] += 1
        if discards[suit][rank] == maxDiscards[rank]:
            maxScore[suit] = min(maxScore[suit], rank)
    return maxScore

def find_tempo(r):
    partner_idx = (r.whoseTurn + 1) % r.nPlayers
    partner_hand = newest_to_oldest(r.h[partner_idx].cards)
    for slot in get_slots_currently_touched(partner_hand):
        card = partner_hand[slot]
        if len(set(card["direct"])) == 1 and is_playable(card, r.progress):
            if card["direct"][0] in SUIT_CONTENTS:
                return partner_idx, card["name"][1]
            else:
                return partner_idx, card["name"][0]

def find_fix(r):
    partner_idx = (r.whoseTurn + 1) % r.nPlayers
    partner_hand = newest_to_oldest(r.h[partner_idx].cards)
    for slot in get_slots_currently_touched(partner_hand):
        card = partner_hand[slot]
        if len(set(card["direct"])) == 1 and not useful(r, card["name"]):
            if card["direct"][0] in SUIT_CONTENTS:
                return partner_idx, card["name"][1]
            else:
                return partner_idx, card["name"][0]


def newest_to_oldest(cards):
    return list(reversed(sorted(cards, key = lambda card: card["time"])))

def get_slots_touched(hand, hint_value):
    return [i for i, card in enumerate(hand) if hint_value in card["direct"]]

def get_slots_hypothetically_touched(hand, hint_value):
    return [i for i, card in enumerate(hand) if hint_value in card["name"]]

def get_focus(slots_touched):
    if len(slots_touched) == 0:
        return None
    if len(slots_touched) == 1:
        return slots_touched[0]
    if slots_touched[0] == 0:
        return slots_touched[1]
    return slots_touched[0]

def get_slots_previously_touched(hand, hint_value):
    return [i for i, card in enumerate(hand) if previously_touched(card, hint_value)]

def get_slots_currently_touched(hand):
    return [i for i, card in enumerate(hand) if currently_touched(card)]

def previously_touched(card, hint_value):
    return card["direct"] != [] and card["direct"] != [hint_value]

def currently_touched(card):
    return card["direct"] != []

def get_referenced_card(hand, focus, previously_touched):
    slot = (focus - 1 + len(hand)) % len(hand)
    while slot in previously_touched:
        slot = (slot - 1 + len(hand)) % len(hand)
    return hand[slot]

def useful(r, card_name):
    suit = card_name[1]
    rank = int(card_name[0])
    return r.progress[suit] < rank and rank <= maxStacks(r)[suit]
