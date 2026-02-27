class ADSException(Exception):
    """Base exception for ADS System"""
    pass

class DocumentNotFoundError(ADSException):
    """Raised when a document is not found"""
    pass

class RuleGroupNotFoundError(ADSException):
    """Raised when a rule group is not found"""
    pass

class LLMError(ADSException):
    """Raised when LLM service fails"""
    pass