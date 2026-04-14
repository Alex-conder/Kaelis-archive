"""
Triple Factory - Auto-generated test data factory
Generated at: 2026-04-13T00:52:56.715630
*** DO NOT MODIFY MANUALLY ***
"""

import factory
from datetime import datetime
from typing import Optional

try:
    from api.models.triple import Triple
except ImportError:
    Triple = object  # Fallback for type hints


class TripleFactory(factory.Factory):
    """
    Factory for creating Triple test instances
        class Meta:
        model = Triple
        # sqlalchemy_session = db_session  # TODO: Configure your session
    
    subject = " metabolite"
    predicate = "has_function"
    object = "antioxidant"
    confidence = 0.95
    metadata = factory.LazyFunction(dict)
    
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)

    @factory.post_generation
    def with_relations(obj, create, extracted, **kwargs):
        """Hook to add relations after creation"""
        pass
