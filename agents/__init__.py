# Cash Mashine Agents
from .base_agent import BaseMoneyAgent, MoneyIdea
from .survey_agent import SurveyAgent
from .airdrop_agent import AirdropAgent
from .gift_agent import GiftAgent
from .cashback_agent import CashbackAgent
from .passive_agent import PassiveAgent
from .gig_agent import GigAgent

__all__ = [
    "BaseMoneyAgent", "MoneyIdea",
    "SurveyAgent", "AirdropAgent", "GiftAgent",
    "CashbackAgent", "PassiveAgent", "GigAgent",
]
