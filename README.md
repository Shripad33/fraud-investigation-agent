\# Fraud Investigation Agent — Hacker House Goa



An explainable fraud investigation agent built for the Hacker House Goa challenge.



\## What It Does



The system investigates suspicious financial transactions using:



\- Transaction history

\- Customer behavior

\- Identity and device evidence

\- Cross-customer activity

\- Similar transaction patterns

\- Historical closed fraud cases

\- Rule-based investigation decisions

\- TigerGraph relationship modeling



The investigation produces an explainable case record containing evidence, findings, decisions, actions, and recommended next steps.



\## Architecture



```text

Case Pack

&#x20;  |

&#x20;  v

Investigation Agent

&#x20;  |

&#x20;  +--> Transaction History

&#x20;  |

&#x20;  +--> Customer Behavior

&#x20;  |

&#x20;  +--> Identity / Device Evidence

&#x20;  |

&#x20;  +--> Historical Closed Cases

&#x20;  |

&#x20;  +--> Cross-Customer Activity

&#x20;  |

&#x20;  v

Evidence Analysis

&#x20;  |

&#x20;  v

Fraud Decision

&#x20;  |

&#x20;  +--> Verdict

&#x20;  +--> Fraud Probability

&#x20;  +--> Pattern

&#x20;  +--> Exposure

&#x20;  +--> Next Best Action

&#x20;  +--> Evidence Requests

&#x20;  +--> SAR Assessment

&#x20;  |

&#x20;  v

Case Investigation JSON

