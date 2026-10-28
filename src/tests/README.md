# Play-testing new cards

Nothing here runs automatically, because the game can only be driven through its GUI. Each deck in `decks/` covers one mechanic. To use them:

1. Build them into the game's `Playdeck/` folder with `make test-decks GAME_DIR=..`.
2. Play each deck against itself, or against a normal deck, and work through its checklist.

When you add cards, add them to a deck here and add a line to the checklist.

## kaladesh-energy

- [ ] Hovering over a life total shows "Energy: N" once a player has energy, and it resets to 0 in the next duel.
- [ ] Sage of Shaila's Claim gives 3 energy when it enters the battlefield. Thriving creatures, Riparian Tiger, Voltaic Brawler and Lathnu Hellion each give 2.
- [ ] Thriving creature attacks: you're offered "Pay 2 energy"; paying gives a +1/+1 counter, and the option doesn't appear with fewer than 2 energy.
- [ ] Riparian Tiger: +2/+2 for 2 energy. Voltaic Brawler: +1/+1 and trample for 1.
- [ ] Longtusk Cub gets 2 energy on combat damage to a player; "Pay 2 energy" puts a +1/+1 counter on it.
- [ ] Whirler Virtuoso: "Pay 3 energy" makes a flying Thopter. Can't be activated with less than 3.
- [ ] Lathnu Hellion: at your end step, pay 2 energy or it's sacrificed. The opponent's end step does nothing.
- [ ] Harnessed Lightning: gives 3 energy, asks how much to pay, deals that much damage. The AI pays just enough to kill.
- [ ] Glimmer of Genius (scry 2, draw 2, 2 energy), Live Fast (draw 2, lose 2, 2 energy), Attune with Aether (basic land to hand, 2 energy).
- [ ] Saving and loading mid-duel keeps both players' energy.

## kaladesh-fabricate-vehicles

- [ ] Fabricate offers counters or Servos. Counters go on the creature; Servos are 1/1 colorless artifact creatures. Fabricate 2 makes 2 of either.
- [ ] Glint-Sleeve Artisan, Propeller Pioneer (flying) and Peema Outrider (trample) all fabricate, since they share one function.
- [ ] A vehicle can't attack or block until crewed. Crewing asks for creatures until their total power reaches N, taps them, and makes the vehicle an artifact creature with its printed power and toughness until end of turn.
- [ ] Crewing works with creatures that came in this turn (crewing isn't a tap ability of the creature), and can be cancelled partway without tapping anything.
- [ ] Ovalchase Dragster and Fleetwheel Cruiser have haste once crewed. Fleetwheel Cruiser is a creature the turn it enters without crewing.
- [ ] Renegade Freighter gets +1/+1 and trample when it attacks. Bomat Bazaar Barge draws a card when it enters.
- [ ] The AI crews on its own turn before attacking, or on yours before blocking, not at random times.

## monarch

- [ ] Palace Sentinels or Custodi Lich entering the battlefield makes you the monarch. A "The Monarch" emblem appears under your control, and only one exists.
- [ ] The monarch draws a card at their end step.
- [ ] Combat damage to the monarch from a creature moves the emblem to that creature's controller.
- [ ] Throne Warden (+1/+1 counter) and Garrulous Sycophant (drain 1) trigger at your end step only while you're the monarch.
- [ ] Stun and Renegade Tactics: the target can't block this turn, and you draw a card. No card if the target became illegal.
