# Chapter 1 flow (generated)

Generated with `factgraph graph --chapter 1 --config examples/lighthouse/factgraph.toml`. Red dashed boxes are unreachable beats.

```mermaid
flowchart LR
  subgraph g1["harbour_master.dialogue"]
    n1["dialogue/harbour_master:4<br/><i>dialogue_line</i>"]:::beat
    n2["dialogue/harbour_master:6<br/><i>dialogue_line</i>"]:::unreachable
    n3["dialogue/harbour_master:7 (+1 lines)<br/><i>choice</i>"]:::beat
    n4["dialogue/harbour_master:9<br/><i>dialogue_effect</i>"]:::beat
  end
  subgraph g2["harbour"]
    n5["enter.harbour<br/><i>location</i>"]:::beat
    n6["harbour_master<br/><i>interactable</i>"]:::beat
    n7["cliff_ladder<br/><i>interactable</i>"]:::beat
  end
  subgraph g3["lighthouse"]
    n8["enter.lighthouse<br/><i>location</i>"]:::beat
    n9["keeper_desk<br/><i>interactable</i>"]:::beat
    n10["lamp_room<br/><i>interactable</i>"]:::beat
    n11["relight_lamp<br/><i>interactable</i>"]:::beat
  end
  subgraph g4["boathouse"]
    n12["enter.boathouse<br/><i>location</i>"]:::beat
    n13["empty_mooring<br/><i>interactable</i>"]:::beat
  end
  subgraph g5["island"]
    n14["island_footprints<br/><i>interactable</i>"]:::unreachable
  end
  n15["deduction.keeper_left_by_boat<br/><i>deduction</i>"]:::beat
  n16["deduction.keeper_rowed_to_island<br/><i>deduction</i>"]:::unreachable
  n17(["case.island.searched"]):::fact
  n18(["case.keeper.state"]):::fact
  n19(["chapter.1.started"]):::fact
  n20(["clue.boat.missing"]):::fact
  n21(["clue.boat.missng"]):::fact
  n22(["clue.harbour.testimony"]):::fact
  n23(["clue.island.footprints"]):::fact
  n24(["clue.keeper.found"]):::fact
  n25(["clue.lamp.cold"]):::fact
  n26(["clue.lighthouse.leter"]):::fact
  n27(["clue.lighthouse.letter"]):::fact
  n28(["clues.found"]):::fact
  n29(["item.rope"]):::fact
  n30(["lamp.lit"]):::fact
  n31(["stats.cliff_climbed"]):::fact
  n32(["stats.desk_opened"]):::fact
  n33{{"chapter.1.complete"}}:::goal
  n4 --> n22
  n9 --> n27
  n9 -- "+1" --> n28
  n9 --> n32
  n10 --> n25
  n10 -- "+1" --> n28
  n13 --> n20
  n13 -- "+1" --> n28
  n6 --> n29
  n7 --> n31
  n14 --> n23
  n11 --> n30
  n15 -- "= 'solved'" --> n18
  n16 --> n17
  n27 --> n1
  n24 --> n2
  n21 --> n3
  n21 --> n4
  n19 --> n5
  n19 --> n8
  n27 --> n12
  n30 -. "not" .-> n10
  n26 --> n13
  n28 -- "> 1" --> n6
  n29 --> n7
  n17 --> n14
  n20 --> n15
  n25 --> n15
  n22 --> n15
  n18 -- "= 'open'" --> n15
  n23 --> n16
  n18 -- "= 'solved'" --> n33
  classDef beat fill:#eef,stroke:#446
  classDef fact fill:#efe,stroke:#464
  classDef goal fill:#ffe,stroke:#864
  classDef unreachable fill:#fee,stroke:#c00,stroke-dasharray:4
```
