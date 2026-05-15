# Copyright (c) 2026, ebamadernis@gmail.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class PayEmployeeCategoryDetail(Document):
    pass

@frappe.whitelist()
def get_working_day(currency=None):
    """
    Récupère le nombre de jours ouvrables depuis les paramètres de paie
    
    Args:
        currency (str, optional): La devise pour laquelle récupérer les jours ouvrables
        
    Returns:
        dict: Dictionnaire contenant le nombre de jours ouvrables
    """
    
    # Vérifier si la devise est fournie
    if not currency:
        frappe.throw("Devise non fournie")
    
    # Récupérer les paramètres de paie
    payroll_settings = frappe.get_single("Pay Payroll Settings")
    
    # Vérifier si le champ working_day existe
    if not hasattr(payroll_settings, 'working_day') or not payroll_settings.working_day:
        frappe.throw("Le nombre de jours ouvrables n'est pas configuré dans les paramètres de paie")
    
    working_day = payroll_settings.working_day
    
    # Validation du nombre de jours
    if working_day <= 0:
        frappe.throw("Le nombre de jours ouvrables doit être supérieur à zéro")
    
    # Retourner le résultat
    return {
        "working_day": working_day,
        "currency": currency
    }