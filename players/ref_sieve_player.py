"""Referential Sieve Player
"""

from hanabi_classes import *
from bot_utils import is_playable

class ReferentialSievePlayer(AIPlayer):

    @classmethod
    def get_name(cls):
        return 'ref_sieve'

    def __init__(self, *args):
        """Can be overridden to perform initialization, but must call super"""
        super(ReferentialSievePlayer, self).__init__(*args)

    def play(self, r):
        play = get_play(r)
        if play:
            return 'play', play
        hint = find_hint(r)
        if hint and r.hints > 0:
            return 'hint', hint
        my_hand = newest_to_oldest(r.h[r.whoseTurn].cards)
        if r.hints == 8:
            return 'hint', find_stall(r)
        return 'discard', my_hand[0]



    def end_game_logging(self):
        """Can be overridden to perform logging at the end of the game"""
        pass

def get_play(r):
    if len(r.playHistory) == 0:
        return None
    my_hand = newest_to_oldest(r.h[r.whoseTurn].cards)

    most_recent_move_type, most_recent_move = r.playHistory[-1]
    if most_recent_move_type == 'hint':
        _who, most_recent_hint = most_recent_move
        if most_recent_hint in SUIT_CONTENTS:
            return None
        slots_touched = get_own_slots_touched(my_hand, most_recent_hint)
        focus = get_focus(slots_touched)
        return wrap_around(my_hand, focus - 1)

    return None

def find_hint(r):
    partner_idx = (r.whoseTurn + 1) % r.nPlayers
    partner_hand = newest_to_oldest(r.h[partner_idx].cards)
    for color in possible_color_hints(partner_hand):
        slots_touched = get_others_slots_touched(partner_hand, color)
        focus = get_focus(slots_touched)
        referenced_card = wrap_around(partner_hand, focus - 1)
        # print('candidate hint:', color, slots_touched, focus)
        if is_playable(referenced_card, r.progress):
            return partner_idx, color
    return None

def find_stall(r):
    partner_idx = (r.whoseTurn + 1) % r.nPlayers
    partner_hand = newest_to_oldest(r.h[partner_idx].cards)
    return partner_idx, partner_hand[-1]["name"][0]

def possible_color_hints(partner_hand):
    result = []
    for card in partner_hand:
        suit = card["name"][1]
        if suit not in result:
            result.append(suit)

    return result

def newest_to_oldest(cards):
    return list(reversed(sorted(cards, key = lambda card: card["time"])))

def get_own_slots_touched(my_hand, hint_value):
    return [i for i, card in enumerate(my_hand) if hint_value in card["direct"]]

def get_others_slots_touched(their_hand, hint_value):
    return [i for i, card in enumerate(their_hand) if hint_value in card["name"]]

def get_focus(slots_touched):
    if len(slots_touched) == 0:
        return None
    if len(slots_touched) == 1:
        return slots_touched[0]
    if slots_touched[0] == 0:
        return slots_touched[1]
    return slots_touched[0]

def wrap_around(hand, slot):
    wrapped_around = (slot + len(hand)) % len(hand)
    return hand[wrapped_around]
