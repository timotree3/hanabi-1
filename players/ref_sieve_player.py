"""Referential Sieve Player
"""

from hanabi_classes import *
from bot_utils import is_playable, deduce_plays

class ReferentialSievePlayer(AIPlayer):

    @classmethod
    def get_name(cls):
        return 'ref_sieve'

    def __init__(self, *args):
        """Can be overridden to perform initialization, but must call super"""
        super(ReferentialSievePlayer, self).__init__(*args)

    def play(self, r):
        my_hand = newest_to_oldest(r.h[r.whoseTurn].cards)
        play = get_instructed_play(r)
        if play:
            return 'play', play
        deducable_plays = deduce_plays(my_hand, r.progress, r.suits)
        if deducable_plays:
            return 'play', deducable_plays[0]
        hint = find_hint(r)
        if hint and r.hints > 0:
            return 'hint', hint
        if r.hints == 8:
            return 'hint', find_stall(r)
        return 'discard', my_hand[0]



    def end_game_logging(self):
        """Can be overridden to perform logging at the end of the game"""
        pass

def get_instructed_play(r):
    if len(r.playHistory) == 0:
        return None
    my_hand = newest_to_oldest(r.h[r.whoseTurn].cards)

    most_recent_move_type, most_recent_move = r.playHistory[-1]
    if most_recent_move_type == 'hint':
        _who, most_recent_hint = most_recent_move
        if most_recent_hint in SUIT_CONTENTS:
            return None
        slots_touched = get_slots_touched(my_hand, most_recent_hint)
        slots_newly_touched = [slot for slot in slots_touched if not previously_touched(my_hand[slot], most_recent_hint)]
        focus = get_focus(slots_newly_touched)
        return get_referenced_card(my_hand, focus, get_slots_previously_touched(my_hand, most_recent_hint))

    return None

def find_hint(r):
    partner_idx = (r.whoseTurn + 1) % r.nPlayers
    partner_hand = newest_to_oldest(r.h[partner_idx].cards)
    for card in partner_hand:
        hypothetical_color = card["name"][1]
        slots_touched = get_slots_hypothetically_touched(partner_hand, hypothetical_color)
        slots_newly_touched = [slot for slot in slots_touched if not currently_touched(partner_hand[slot])]
        if len(slots_newly_touched) == 0:
            continue
        focus = get_focus(slots_newly_touched)
        slots_currently_touched = get_slots_currently_touched(partner_hand)
        referenced_card = get_referenced_card(partner_hand, focus, slots_currently_touched)
        print('hint', (hypothetical_color, slots_newly_touched, focus, slots_currently_touched, referenced_card))
        if is_playable(referenced_card, r.progress):
            return partner_idx, hypothetical_color
    return None

def find_stall(r):
    partner_idx = (r.whoseTurn + 1) % r.nPlayers
    partner_hand = newest_to_oldest(r.h[partner_idx].cards)
    return partner_idx, partner_hand[-1]["name"][0]

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
