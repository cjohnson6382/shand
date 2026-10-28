// -*- c-basic-offset:2 -*-
#include "manalink.h"

/***** Functions *****/

/* The monarch is whoever controls the one "The Monarch" emblem, so it's saved along with the rest of the battlefield and needs no other state. */
int is_monarch(int player)
{
  return check_battlefield_for_id(player, CARD_ID_THE_MONARCH);
}

// "You become the monarch": take the emblem from the opponent, or create it if nobody has it yet.
void become_monarch(int player, int card)
{
  if (is_monarch(player))
	return;

  int c;
  for (c = 0; c < active_cards_count[1-player]; ++c)
	if (in_play(1-player, c) && get_id(1-player, c) == CARD_ID_THE_MONARCH)
	  {
		give_control(player, card, 1-player, c);
		return;
	  }

  generate_token_by_id(player, card, CARD_ID_THE_MONARCH);
}

/***** Cards *****/

int card_the_monarch(int player, int card, event_t event)
{
  /* The Monarch	""	0x200f0f7
   * Emblem
   * At the beginning of your end step, draw a card.
   * Whenever a creature deals combat damage to you, its controller becomes the monarch. */

  if (current_turn == player && eot_trigger(player, card, event))
	draw_a_card(player);

  // As card_contested_war_zone().
  card_instance_t* damage = combat_damage_being_dealt(event);
  if (damage
	  && damage->damage_target_player == player && damage->damage_target_card == -1
	  && !check_special_flags(damage->damage_source_player, damage->damage_source_card, SF_ATTACKING_PWALKER)
	  && (damage->targets[3].player & TYPE_CREATURE)
	  && damage->damage_source_player != player)
	give_control_of_self(player, card);

  return 0;
}

/*** White ***/

int card_throne_warden(int player, int card, event_t event)
{
  /* Throne Warden	|1|W	0x200f07a
   * Creature - Human Soldier 1/1
   * At the beginning of your end step, if you're the monarch, put a +1/+1 counter on ~. */

  if (current_turn == player && is_monarch(player) && eot_trigger(player, card, event))
	add_1_1_counter(player, card);

  return 0;
}

/*** Black ***/

int card_custodi_lich(int player, int card, event_t event)
{
  /* Custodi Lich	|3|B|B	0x200f061
   * Creature - Zombie Cleric 4/2
   * When ~ enters the battlefield, you become the monarch.
   * Whenever you become the monarch, target player sacrifices a creature. */
  /* Also Knights of the Black Rose and Palace Sentinels, which share this function's slot.  Only the part all three have in common - becoming the monarch when
   * it enters the battlefield - is implemented so far; Custodi Lich's and Knights of the Black Rose's second abilities still need doing. */

  if (comes_into_play(player, card, event))
	become_monarch(player, card);

  return 0;
}

int card_garrulous_sycophant(int player, int card, event_t event)
{
  /* Garrulous Sycophant	|2|B	0x200f0a2
   * Creature - Human Advisor 3/2
   * At the beginning of your end step, if you're the monarch, each opponent loses 1 life and you gain 1 life. */

  if (current_turn == player && is_monarch(player) && eot_trigger(player, card, event))
	{
	  lose_life(1-player, 1);
	  gain_life(player, 1);
	}

  return 0;
}
