// -*- c-basic-offset:2 -*-
#include "manalink.h"

/***** Functions *****/

/* Fabricate N (When this creature enters the battlefield, put N +1/+1 counters on it or create N 1/1 colorless Servo artifact creature tokens.) */
void fabricate(int player, int card, event_t event, int n)
{
  if (comes_into_play(player, card, event))
	{
	  enum
	  {
		CHOICE_COUNTERS = 1,
		CHOICE_SERVOS
	  } choice = DIALOG(player, card, EVENT_ACTIVATE,
						DLG_NO_STORAGE, DLG_NO_CANCEL, DLG_RANDOM,
						n == 1 ? "+1/+1 counter" : "+1/+1 counters",	1, 2,
						n == 1 ? "Servo token" : "Servo tokens",		1, n);

	  if (choice == CHOICE_SERVOS)
		generate_tokens_by_id(player, card, CARD_ID_SERVO, n);
	  else
		add_1_1_counters(player, card, n);
	}
}

// Total power of untapped creatures {player} controls other than {player,card}, which is what can crew it.
static int crew_power_available(int player, int card)
{
  int c, total = 0;
  for (c = 0; c < active_cards_count[player]; ++c)
	if (c != card && in_play(player, c) && is_what(player, c, TYPE_CREATURE) && !is_tapped(player, c))
	  total += get_power(player, c);
  return total;
}

/* Crew's cost: tap any number of untapped creatures you control with total power crew or more.  Chooses them into (player,card)->targets[] and taps them if the
 * total gets there; returns 1 if it did. */
static int tap_creatures_to_crew(int player, int card, int crew)
{
  card_instance_t* instance = get_card_instance(player, card);

  target_definition_t td;
  default_target_definition(player, card, &td, TYPE_CREATURE);
  td.allowed_controller = td.preferred_controller = player;
  td.illegal_state = TARGET_STATE_TAPPED;
  td.illegal_abilities = 0;

  state_untargettable(player, card, 1);
  instance->number_of_targets = 0;
  int i, picked = 0, total = 0;
  while (total < crew && picked < 10 && can_target(&td))
	{
	  char prompt[100];
	  scnprintf(prompt, 100, "Select a creature to crew with (power %d of %d)", total, crew);
	  if (!new_pick_target(&td, prompt, picked, GS_LITERAL_PROMPT))
		break;
	  state_untargettable(instance->targets[picked].player, instance->targets[picked].card, 1);
	  total += get_power(instance->targets[picked].player, instance->targets[picked].card);
	  ++picked;
	}

  state_untargettable(player, card, 0);
  for (i = 0; i < picked; ++i)
	{
	  state_untargettable(instance->targets[i].player, instance->targets[i].card, 0);
	  if (total >= crew)
		tap_card(instance->targets[i].player, instance->targets[i].card);
	}
  instance->number_of_targets = 0;

  return total >= crew;
}

/* Crew N (Tap any number of creatures you control with total power N or more: This Vehicle becomes an artifact creature until end of turn.)
 * sp_keywords are added while it's a creature - Haste, for instance, which vehicles can't otherwise have since it's only granted by code. */
int vehicle(int player, int card, event_t event, int crew, sp_keyword_t sp_keywords)
{
  if (!IS_ACTIVATING(event))
	return 0;

  if (event == EVENT_CAN_ACTIVATE)
	{
	  if (is_what(player, card, TYPE_CREATURE) || crew_power_available(player, card) < crew)
		return 0;

	  // The AI crews just before attacking or blocking, rather than whenever it can.
	  if (IS_AI(player)
		  && !(current_turn == player && current_phase <= PHASE_MAIN1)
		  && !(current_turn != player && current_phase == PHASE_BEFORE_BLOCKING))
		return 0;

	  return generic_activated_ability(player, card, event, GAA_NONE, MANACOST0, 0, NULL, NULL);
	}

  if (event == EVENT_ACTIVATE)
	{
	  if (charge_mana_for_activated_ability(player, card, MANACOST0) && !tap_creatures_to_crew(player, card, crew))
		spell_fizzled = 1;
	}

  if (event == EVENT_RESOLVE_ACTIVATION)
	{
	  // {player,card} is the activation here, so work on the vehicle itself.
	  card_instance_t* instance = get_card_instance(player, card);
	  int p = instance->parent_controller, c = instance->parent_card;
	  if (in_play(p, c))
		animate_self(p, c, get_base_power(p, c), get_base_toughness(p, c), 0, sp_keywords, 0, 0);
	}

  return 0;
}

// "Pay {E}...{E}: [effect]" activated abilities, as a CAN_ACTIVATE/ACTIVATE frontend.  Returns 1 during EVENT_RESOLVE_ACTIVATION.
static int energy_activated_ability(int player, int card, event_t event, int energy, int mode)
{
  if (event == EVENT_CAN_ACTIVATE)
	return ENERGY_COUNTERS(player) >= energy && generic_activated_ability(player, card, event, mode, MANACOST0, 0, NULL, NULL);

  if (event == EVENT_ACTIVATE)
	{
	  if (charge_mana_for_activated_ability(player, card, MANACOST0) && !pay_energy(player, energy))
		spell_fizzled = 1;
	}

  return event == EVENT_RESOLVE_ACTIVATION;
}

/***** Cards *****/

/*** Several cards sharing one slot ***/

int card_thriving_grubs(int player, int card, event_t event)
{
  /* Thriving Grubs	|1|R	0x200f16f
   * Creature - Gremlin 2/1
   * When ~ enters the battlefield, you get |E|E (two energy counters).
   * Whenever ~ attacks, you may pay |E|E. If you do, put a +1/+1 counter on it. */
  /* Also Thriving Ibex, Thriving Rats, Thriving Rhino, and Thriving Turtle, which share this function's slot. */

  if (comes_into_play(player, card, event))
	add_energy(player, 2);

  if (declare_attackers_trigger(player, card, event, 0, player, card) && pay_energy_optional(player, card, 2, NULL))
	add_1_1_counter(player, card);

  return 0;
}

int card_accomplished_automaton(int player, int card, event_t event)
{
  /* Accomplished Automaton	|7	0x200f147
   * Artifact Creature - Construct 5/7
   * Fabricate 1 */
  /* Also Glint-Sleeve Artisan, Peema Outrider, and Propeller Pioneer, which share this function's slot.  Their flying and trample come from ct_all.csv. */

  fabricate(player, card, event, 1);
  return 0;
}

int card_stun(int player, int card, event_t event)
{
  /* Stun	|1|R	0x200f304
   * Instant
   * Target creature can't block this turn.
   * Draw a card. */
  /* Also Renegade Tactics, which shares this function's slot and has the same text. */

  if (!IS_GS_EVENT(player, card, event))
	return 0;

  target_definition_t td;
  default_target_definition(player, card, &td, TYPE_CREATURE);

  if (event == EVENT_RESOLVE_SPELL)
	{
	  if (valid_target(&td))
		{
		  card_instance_t* instance = get_card_instance(player, card);
		  pump_ability_until_eot(player, card, instance->targets[0].player, instance->targets[0].card, 0, 0, 0, SP_KEYWORD_CANNOT_BLOCK);
		  draw_a_card(player);
		}
	  kill_card(player, card, KILL_DESTROY);
	}

  return generic_spell(player, card, event, GS_CAN_TARGET, &td, "TARGET_CREATURE", 1, NULL);
}

/*** White ***/

int card_visionary_augmenter(int player, int card, event_t event)
{
  /* Visionary Augmenter	|2|W|W	0x200f179
   * Creature - Dwarf Artificer 2/1
   * Fabricate 2 */

  fabricate(player, card, event, 2);
  return 0;
}

/*** Blue ***/

int card_glimmer_of_genius(int player, int card, event_t event)
{
  /* Glimmer of Genius	|3|U	0x200f1bf
   * Instant
   * Scry 2, then draw two cards. You get |E|E (two energy counters). */

  if (event == EVENT_RESOLVE_SPELL)
	{
	  scry(player, 2);
	  draw_cards(player, 2);
	  add_energy(player, 2);
	  kill_card(player, card, KILL_DESTROY);
	}

  return basic_spell(player, card, event);
}

/*** Black ***/

int card_live_fast(int player, int card, event_t event)
{
  /* Live Fast	|2|B	0x200f25a
   * Sorcery
   * You draw two cards, lose 2 life, and get |E|E (two energy counters). */

  if (event == EVENT_RESOLVE_SPELL)
	{
	  draw_cards(player, 2);
	  lose_life(player, 2);
	  add_energy(player, 2);
	  kill_card(player, card, KILL_DESTROY);
	}

  return basic_spell(player, card, event);
}

int card_maulfist_squad(int player, int card, event_t event)
{
  /* Maulfist Squad	|3|B	0x200f26e
   * Creature - Human Artificer 3/1
   * Menace
   * Fabricate 1 */

  menace(player, card, event);
  fabricate(player, card, event, 1);
  return 0;
}

int card_weaponcraft_enthusiast(int player, int card, event_t event)
{
  /* Weaponcraft Enthusiast	|2|B	0x200f2a0
   * Creature - Aetherborn Artificer 0/1
   * Fabricate 2 */

  fabricate(player, card, event, 2);
  return 0;
}

/*** Red ***/

int card_harnessed_lightning(int player, int card, event_t event)
{
  /* Harnessed Lightning	|1|R	0x200f2d2
   * Instant
   * Choose target creature. You get |E|E|E (three energy counters), then you may pay any amount of |E. ~ deals that much damage to that creature. */

  if (!IS_GS_EVENT(player, card, event))
	return 0;

  target_definition_t td;
  default_target_definition(player, card, &td, TYPE_CREATURE);

  if (event == EVENT_RESOLVE_SPELL)
	{
	  if (valid_target(&td))
		{
		  card_instance_t* instance = get_card_instance(player, card);
		  add_energy(player, 3);

		  int amount;
		  if (IS_AI(player))
			{
			  // Enough to kill an opponent's creature if possible; nothing for its own.
			  amount = 0;
			  if (instance->targets[0].player != player)
				{
				  amount = get_toughness(instance->targets[0].player, instance->targets[0].card);
				  if (amount > ENERGY_COUNTERS(player))
					amount = ENERGY_COUNTERS(player);
				}
			}
		  else
			amount = choose_a_number(player, "Pay how much energy?", ENERGY_COUNTERS(player));

		  if (amount > 0 && pay_energy(player, amount))
			damage_target0(player, card, amount);
		}

	  kill_card(player, card, KILL_DESTROY);
	}

  return generic_spell(player, card, event, GS_CAN_TARGET, &td, "TARGET_CREATURE", 1, NULL);
}

int card_lathnu_hellion(int player, int card, event_t event)
{
  /* Lathnu Hellion	|2|R	0x200f2e6
   * Creature - Hellion 4/4
   * Haste
   * When ~ enters the battlefield, you get |E|E (two energy counters).
   * At the beginning of your end step, sacrifice ~ unless you pay |E|E. */

  haste(player, card, event);

  if (comes_into_play(player, card, event))
	add_energy(player, 2);

  if (current_turn == player && eot_trigger(player, card, event)
	  && !pay_energy_optional(player, card, 2, "Pay 2 energy (or sacrifice it)"))
	kill_card(player, card, KILL_SACRIFICE);

  return 0;
}

/*** Green ***/

int card_attune_with_aether(int player, int card, event_t event)
{
  /* Attune with Aether	|G	0x200f34a
   * Sorcery
   * Search your library for a basic land card, reveal it, put it into your hand, then shuffle your library. You get |E|E (two energy counters). */

  if (event == EVENT_RESOLVE_SPELL)
	{
	  tutor_basic_land(player, 0, 0);
	  add_energy(player, 2);
	  kill_card(player, card, KILL_DESTROY);
	}

  return basic_spell(player, card, event);
}

int card_highspire_artisan(int player, int card, event_t event)
{
  /* Highspire Artisan	|2|G	0x200f377
   * Creature - Elf Artificer 0/3
   * Reach
   * Fabricate 1 */

  fabricate(player, card, event, 1);
  return 0;
}

int card_longtusk_cub(int player, int card, event_t event)
{
  /* Longtusk Cub	|1|G	0x200f386
   * Creature - Cat 2/2
   * Whenever ~ deals combat damage to a player, you get |E|E (two energy counters).
   * Pay |E|E: Put a +1/+1 counter on ~. */

  if (has_combat_damage_been_inflicted_to_a_player(player, card, event))
	add_energy(player, 2);

  if (energy_activated_ability(player, card, event, 2, GAA_NONE))
	{
	  card_instance_t* instance = get_card_instance(player, card);
	  if (in_play(instance->parent_controller, instance->parent_card))
		add_1_1_counter(instance->parent_controller, instance->parent_card);
	}

  return 0;
}

int card_riparian_tiger(int player, int card, event_t event)
{
  /* Riparian Tiger	|3|G|G	0x200f3a4
   * Creature - Cat 4/4
   * Trample
   * When ~ enters the battlefield, you get |E|E (two energy counters).
   * Whenever ~ attacks, you may pay |E|E. If you do, it gets +2/+2 until end of turn. */

  if (comes_into_play(player, card, event))
	add_energy(player, 2);

  if (declare_attackers_trigger(player, card, event, 0, player, card) && pay_energy_optional(player, card, 2, NULL))
	pump_until_eot(player, card, player, card, 2, 2);

  return 0;
}

int card_sage_of_shailas_claim(int player, int card, event_t event)
{
  /* Sage of Shaila's Claim	|1|G	0x200f3a9
   * Creature - Elf Druid 2/1
   * When ~ enters the battlefield, you get |E|E|E (three energy counters). */

  if (comes_into_play(player, card, event))
	add_energy(player, 3);

  return 0;
}

/*** Multi ***/

int card_voltaic_brawler(int player, int card, event_t event)
{
  /* Voltaic Brawler	|R|G	0x200f40d
   * Creature - Human Warrior 3/2
   * When ~ enters the battlefield, you get |E|E (two energy counters).
   * Whenever ~ attacks, you may pay |E. If you do, it gets +1/+1 and gains trample until end of turn. */

  if (comes_into_play(player, card, event))
	add_energy(player, 2);

  if (declare_attackers_trigger(player, card, event, 0, player, card) && pay_energy_optional(player, card, 1, NULL))
	pump_ability_until_eot(player, card, player, card, 1, 1, KEYWORD_TRAMPLE, 0);

  return 0;
}

int card_whirler_virtuoso(int player, int card, event_t event)
{
  /* Whirler Virtuoso	|1|U|R	0x200f412
   * Creature - Vedalken Artificer 2/3
   * When ~ enters the battlefield, you get |E|E|E (three energy counters).
   * Pay |E|E|E: Create a 1/1 colorless Thopter artifact creature token with flying. */

  if (comes_into_play(player, card, event))
	add_energy(player, 3);

  if (energy_activated_ability(player, card, event, 3, GAA_NONE))
	generate_token_by_id(player, card, CARD_ID_THOPTER);

  return 0;
}

/*** Artifact ***/

int card_aradara_express(int player, int card, event_t event)
{
  /* Aradara Express	|5	0x200f421
   * Artifact - Vehicle 8/6
   * Menace
   * Crew 4 */

  menace(player, card, event);
  return vehicle(player, card, event, 4, 0);
}

int card_bomat_bazaar_barge(int player, int card, event_t event)
{
  /* Bomat Bazaar Barge	|4	0x200f42b
   * Artifact - Vehicle 5/5
   * When ~ enters the battlefield, draw a card.
   * Crew 3 */

  if (comes_into_play(player, card, event))
	draw_a_card(player);

  return vehicle(player, card, event, 3, 0);
}

int card_fleetwheel_cruiser(int player, int card, event_t event)
{
  /* Fleetwheel Cruiser	|4	0x200f46c
   * Artifact - Vehicle 5/3
   * Trample, haste
   * When ~ enters the battlefield, it becomes an artifact creature until end of turn.
   * Crew 1 */

  if (comes_into_play(player, card, event))
	animate_self(player, card, get_base_power(player, card), get_base_toughness(player, card), 0, SP_KEYWORD_HASTE, 0, 0);

  return vehicle(player, card, event, 1, SP_KEYWORD_HASTE);
}

int card_iron_league_steed(int player, int card, event_t event)
{
  /* Iron League Steed	|4	0x200f485
   * Artifact Creature - Construct 2/2
   * Haste
   * Fabricate 1 */

  haste(player, card, event);
  fabricate(player, card, event, 1);
  return 0;
}

int card_ovalchase_dragster(int player, int card, event_t event)
{
  /* Ovalchase Dragster	|4	0x200f4a3
   * Artifact - Vehicle 6/1
   * Trample, haste
   * Crew 1 */

  return vehicle(player, card, event, 1, SP_KEYWORD_HASTE);
}

int card_renegade_freighter(int player, int card, event_t event)
{
  /* Renegade Freighter	|3	0x200f4b2
   * Artifact - Vehicle 4/3
   * Whenever ~ attacks, it gets +1/+1 and gains trample until end of turn.
   * Crew 2 */

  // Stored in info_slot, since crewing uses targets[].
  if (declare_attackers_trigger(player, card, event, DAT_STORE_IN_INFO_SLOT, player, card))
	pump_ability_until_eot(player, card, player, card, 1, 1, KEYWORD_TRAMPLE, 0);

  return vehicle(player, card, event, 2, 0);
}

int card_sky_skiff(int player, int card, event_t event)
{
  /* Sky Skiff	|2	0x200f4c1
   * Artifact - Vehicle 2/3
   * Flying
   * Crew 1 */

  return vehicle(player, card, event, 1, 0);
}
