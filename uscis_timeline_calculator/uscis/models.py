"""
Data models for the USCIS Timeline Calculator.

This module defines data structures used throughout the application.
"""

import datetime
from dataclasses import dataclass
from typing import List, Dict, Optional, Any, Union


@dataclass
class ProcessingTimeData:
    """Represents processing time data for a specific form and service center."""
    
    form_number: str
    form_description: str
    service_center: str
    min_months: float
    median_months: float
    max_months: float
    last_updated: str
    receipt_date_for_case_inquiry: str


@dataclass
class FormInfo:
    """Represents information about a USCIS form."""
    
    form_number: str
    form_description: str
    service_center: str


@dataclass
class FilingInfo:
    """Represents information about a specific filing."""
    
    filing_date: str
    days_since_filing: int
    progress_percent: int


@dataclass
class ProcessingTime:
    """Represents processing time information."""
    
    min_months: float
    median_months: float
    max_months: float
    expedited: bool
    premium_processing: bool


@dataclass
class EstimatedTimeline:
    """Represents estimated completion timeline."""
    
    earliest_date: str
    median_date: str
    latest_date: str


@dataclass
class CaseStatus:
    """Represents current case status information."""
    
    current_status: str
    can_submit_inquiry: bool
    inquiry_eligibility_date: str


@dataclass
class DataSource:
    """Represents information about the data source."""
    
    last_updated: str
    next_update: str


@dataclass
class Timeline:
    """Represents a complete processing timeline."""
    
    form_info: FormInfo
    filing_info: FilingInfo
    processing_time: ProcessingTime
    estimated_timeline: EstimatedTimeline
    case_status: CaseStatus
    data_source: DataSource
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Timeline':
        """
        Create a Timeline instance from a dictionary.
        
        Args:
            data: Dictionary containing timeline data
            
        Returns:
            A Timeline instance
        """
        return cls(
            form_info=FormInfo(**data['form_info']),
            filing_info=FilingInfo(**data['filing_info']),
            processing_time=ProcessingTime(**data['processing_time']),
            estimated_timeline=EstimatedTimeline(**data['estimated_timeline']),
            case_status=CaseStatus(**data['case_status']),
            data_source=DataSource(**data['data_source'])
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the Timeline instance to a dictionary.
        
        Returns:
            A dictionary representation of the Timeline
        """
        return {
            'form_info': {
                'form_number': self.form_info.form_number,
                'form_description': self.form_info.form_description,
                'service_center': self.form_info.service_center
            },
            'filing_info': {
                'filing_date': self.filing_info.filing_date,
                'days_since_filing': self.filing_info.days_since_filing,
                'progress_percent': self.filing_info.progress_percent
            },
            'processing_time': {
                'min_months': self.processing_time.min_months,
                'median_months': self.processing_time.median_months,
                'max_months': self.processing_time.max_months,
                'expedited': self.processing_time.expedited,
                'premium_processing': self.processing_time.premium_processing
            },
            'estimated_timeline': {
                'earliest_date': self.estimated_timeline.earliest_date,
                'median_date': self.estimated_timeline.median_date,
                'latest_date': self.estimated_timeline.latest_date
            },
            'case_status': {
                'current_status': self.case_status.current_status,
                'can_submit_inquiry': self.case_status.can_submit_inquiry,
                'inquiry_eligibility_date': self.case_status.inquiry_eligibility_date
            },
            'data_source': {
                'last_updated': self.data_source.last_updated,
                'next_update': self.data_source.next_update
            }
        }


@dataclass
class FormOption:
    """Represents an option in a form dropdown."""
    
    value: str
    label: str