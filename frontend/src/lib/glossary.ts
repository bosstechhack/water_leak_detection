// Plain-language definitions shown as tooltips and in the Guide tab.
export const GLOSSARY: Record<string, { label: string; text: string }> = {
  pressure: {
    label: 'Pressure (m)',
    text: 'How hard the water pushes in the pipe, written as metres of water column. A leak or a big demand makes pressure fall.',
  },
  flow: {
    label: 'Flow (L/s)',
    text: 'How much water moves through a pipe each second, in litres per second.',
  },
  baseline: {
    label: 'Baseline',
    text: 'The simulated normal day with nothing wrong. Every scenario is compared against it.',
  },
  unaccounted: {
    label: 'Unaccounted flow',
    text: 'Water that leaves a node but is not recorded by any customer meter. Each node gets exactly as much water as its customers use, so water that disappears with no meter behind it is a leak.',
  },
  noise: {
    label: 'Sensor noise',
    text: 'Small random errors in real sensor readings. The system learns how big this noise is, so it does not raise alarms for it.',
  },
  top1: {
    label: 'Top-1',
    text: 'The first node on the list is the real leak. Top-5 means the real leak is somewhere in the first five.',
  },
  hops: {
    label: 'Pipe hops',
    text: 'How many pipes you walk along to get from the predicted node to the real leak. 0 means the exact node was found.',
  },
  confidence: {
    label: 'Confidence',
    text: 'How strongly the classifier prefers its answer over the others. It is a model score, not a guarantee.',
  },
  region: {
    label: 'Search region',
    text: 'The predicted node plus the nodes directly connected to it. If the leak is not at the predicted node, it is most likely here.',
  },
  meters: {
    label: 'Demand meters',
    text: 'Smart meters that report how much water customers draw at each node. With them, a demand change can be told apart from a leak.',
  },
  score: {
    label: 'Leak score',
    text: 'A number used to rank nodes. It combines how much unmetered water disappears at the node with how much the pressure dropped there. Higher means more likely.',
  },
};

export const CATEGORIES: { id: string; label: string; short: string; blurb: string }[] = [
  { id: 'leak', label: 'Leak', short: 'Leak', blurb: 'A pipe crack loses water. Find where.' },
  { id: 'demand_change', label: 'Demand change', short: 'Demand', blurb: 'Customers use more or less water. Not a leak.' },
  { id: 'source_event', label: 'Pump or reservoir', short: 'Pump / source', blurb: 'A pump stops or a reservoir level changes.' },
  { id: 'tank_event', label: 'Tank change', short: 'Tank', blurb: 'A storage tank starts low or is cut off.' },
  { id: 'valve_block', label: 'Blocked pipe', short: 'Blockage', blurb: 'A valve is closed or a pipe is partly blocked.' },
  { id: 'ageing', label: 'Pipe ageing', short: 'Ageing', blurb: 'Old pipes get rougher and waste pressure.' },
  { id: 'normal', label: 'Normal day', short: 'Normal', blurb: 'Nothing wrong, only sensor noise.' },
];

export const CAUSE_ADVICE: Record<string, { title: string; action: string }> = {
  leak: { title: 'Probable leak', action: 'Inspect the top-ranked node first. If nothing is found there, check the highlighted search region around it.' },
  demand_change: { title: 'Demand change (not a leak)', action: 'No repair needed. Customers are using more or less water than usual, for example a hydrant, a factory or a hot day.' },
  source_event: { title: 'Pump or reservoir change', action: 'Check the pumping station and reservoir levels. Many nodes lost pressure together, which a single leak does not cause.' },
  tank_event: { title: 'Tank change', action: 'Check the storage tank level and its valve. The tank is supplying or taking water differently from normal.' },
  valve_block: { title: 'Blocked or closed pipe', action: 'Look for a closed valve or a blocked pipe. Pressure falls downstream of it and rises upstream, and no water is lost.' },
  ageing: { title: 'Pipe ageing', action: 'Pipes are rougher than expected, which wastes pressure everywhere. Plan an inspection or cleaning; there is no single leak.' },
  normal: { title: 'Everything looks normal', action: 'No action needed. Readings match the normal day within sensor noise.' },
};
