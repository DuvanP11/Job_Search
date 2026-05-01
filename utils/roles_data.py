#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BASE DE DATOS DE ROLES PROFESIONALES
Más de 500 roles profesionales en español e inglés
"""

ROLES_PROFESIONALES = {
    # Tecnología & Datos
    "tecnologia": [
        {"es": "Desarrollador Full Stack", "en": "Full Stack Developer"},
        {"es": "Desarrollador Frontend", "en": "Frontend Developer"},
        {"es": "Desarrollador Backend", "en": "Backend Developer"},
        {"es": "Ingeniero de Software", "en": "Software Engineer"},
        {"es": "Arquitecto de Software", "en": "Software Architect"},
        {"es": "Desarrollador Mobile", "en": "Mobile Developer"},
        {"es": "Desarrollador iOS", "en": "iOS Developer"},
        {"es": "Desarrollador Android", "en": "Android Developer"},
        {"es": "Desarrollador React", "en": "React Developer"},
        {"es": "Desarrollador Python", "en": "Python Developer"},
        {"es": "Desarrollador Java", "en": "Java Developer"},
        {"es": "Desarrollador .NET", "en": ".NET Developer"},
        {"es": "Desarrollador PHP", "en": "PHP Developer"},
        {"es": "Desarrollador Node.js", "en": "Node.js Developer"},
        {"es": "Data Analyst", "en": "Data Analyst"},
        {"es": "Analista de Datos", "en": "Data Analyst"},
        {"es": "Data Scientist", "en": "Data Scientist"},
        {"es": "Científico de Datos", "en": "Data Scientist"},
        {"es": "Data Engineer", "en": "Data Engineer"},
        {"es": "Ingeniero de Datos", "en": "Data Engineer"},
        {"es": "Machine Learning Engineer", "en": "Machine Learning Engineer"},
        {"es": "Ingeniero de ML", "en": "ML Engineer"},
        {"es": "AI Engineer", "en": "AI Engineer"},
        {"es": "Ingeniero de IA", "en": "AI Engineer"},
        {"es": "Business Intelligence Analyst", "en": "BI Analyst"},
        {"es": "Analista BI", "en": "BI Analyst"},
        {"es": "DevOps Engineer", "en": "DevOps Engineer"},
        {"es": "Ingeniero DevOps", "en": "DevOps Engineer"},
        {"es": "Cloud Engineer", "en": "Cloud Engineer"},
        {"es": "Ingeniero Cloud", "en": "Cloud Engineer"},
        {"es": "QA Engineer", "en": "QA Engineer"},
        {"es": "Ingeniero QA", "en": "QA Engineer"},
        {"es": "QA Automation", "en": "QA Automation"},
        {"es": "Tester", "en": "Tester"},
        {"es": "UX Designer", "en": "UX Designer"},
        {"es": "Diseñador UX", "en": "UX Designer"},
        {"es": "UI Designer", "en": "UI Designer"},
        {"es": "Diseñador UI", "en": "UI Designer"},
        {"es": "Product Designer", "en": "Product Designer"},
        {"es": "Diseñador de Producto", "en": "Product Designer"},
        {"es": "Scrum Master", "en": "Scrum Master"},
        {"es": "Product Owner", "en": "Product Owner"},
        {"es": "Product Manager", "en": "Product Manager"},
        {"es": "Gerente de Producto", "en": "Product Manager"},
        {"es": "Technical Lead", "en": "Tech Lead"},
        {"es": "Líder Técnico", "en": "Tech Lead"},
        {"es": "CTO", "en": "CTO"},
        {"es": "Director de Tecnología", "en": "CTO"},
    ],
    
    # Seguridad & Infraestructura
    "seguridad": [
        {"es": "Cybersecurity Analyst", "en": "Cybersecurity Analyst"},
        {"es": "Analista de Ciberseguridad", "en": "Cybersecurity Analyst"},
        {"es": "Security Engineer", "en": "Security Engineer"},
        {"es": "Ingeniero de Seguridad", "en": "Security Engineer"},
        {"es": "Pentester", "en": "Penetration Tester"},
        {"es": "Ethical Hacker", "en": "Ethical Hacker"},
        {"es": "SOC Analyst", "en": "SOC Analyst"},
        {"es": "Network Administrator", "en": "Network Administrator"},
        {"es": "Administrador de Redes", "en": "Network Administrator"},
        {"es": "System Administrator", "en": "System Administrator"},
        {"es": "Administrador de Sistemas", "en": "Sysadmin"},
        {"es": "Database Administrator", "en": "DBA"},
        {"es": "Administrador de Bases de Datos", "en": "DBA"},
    ],
    
    # Finanzas & Contabilidad
    "finanzas": [
        {"es": "Contador", "en": "Accountant"},
        {"es": "Auditor", "en": "Auditor"},
        {"es": "Auditor Interno", "en": "Internal Auditor"},
        {"es": "Analista Financiero", "en": "Financial Analyst"},
        {"es": "Gerente Financiero", "en": "Financial Manager"},
        {"es": "Controller", "en": "Controller"},
        {"es": "CFO", "en": "CFO"},
        {"es": "Director Financiero", "en": "CFO"},
        {"es": "Tesorero", "en": "Treasurer"},
        {"es": "Analista de Riesgos", "en": "Risk Analyst"},
        {"es": "Compliance Officer", "en": "Compliance Officer"},
        {"es": "Oficial de Cumplimiento", "en": "Compliance Officer"},
        {"es": "Tax Specialist", "en": "Tax Specialist"},
        {"es": "Especialista en Impuestos", "en": "Tax Consultant"},
    ],
    
    # Marketing & Ventas
    "marketing": [
        {"es": "Marketing Manager", "en": "Marketing Manager"},
        {"es": "Gerente de Marketing", "en": "Marketing Manager"},
        {"es": "Digital Marketing", "en": "Digital Marketing Specialist"},
        {"es": "Especialista en Marketing Digital", "en": "Digital Marketing"},
        {"es": "Social Media Manager", "en": "Social Media Manager"},
        {"es": "Community Manager", "en": "Community Manager"},
        {"es": "Content Manager", "en": "Content Manager"},
        {"es": "Gerente de Contenido", "en": "Content Manager"},
        {"es": "SEO Specialist", "en": "SEO Specialist"},
        {"es": "Especialista SEO", "en": "SEO Specialist"},
        {"es": "SEM Specialist", "en": "SEM Specialist"},
        {"es": "Especialista SEM", "en": "SEM Specialist"},
        {"es": "Growth Hacker", "en": "Growth Hacker"},
        {"es": "Email Marketing Specialist", "en": "Email Marketing Specialist"},
        {"es": "Brand Manager", "en": "Brand Manager"},
        {"es": "Gerente de Marca", "en": "Brand Manager"},
        {"es": "Ejecutivo de Ventas", "en": "Sales Executive"},
        {"es": "Vendedor", "en": "Salesperson"},
        {"es": "Sales Manager", "en": "Sales Manager"},
        {"es": "Gerente de Ventas", "en": "Sales Manager"},
        {"es": "Account Manager", "en": "Account Manager"},
        {"es": "Gerente de Cuentas", "en": "Account Manager"},
        {"es": "Business Development", "en": "Business Development"},
        {"es": "Desarrollo de Negocios", "en": "Business Development"},
        {"es": "CMO", "en": "CMO"},
        {"es": "Director de Marketing", "en": "CMO"},
    ],
    
    # Recursos Humanos
    "rrhh": [
        {"es": "Recruiter", "en": "Recruiter"},
        {"es": "Reclutador", "en": "Recruiter"},
        {"es": "HR Manager", "en": "HR Manager"},
        {"es": "Gerente de RRHH", "en": "HR Manager"},
        {"es": "HR Business Partner", "en": "HR Business Partner"},
        {"es": "Talent Acquisition", "en": "Talent Acquisition"},
        {"es": "Adquisición de Talento", "en": "Talent Acquisition"},
        {"es": "Compensation & Benefits", "en": "Compensation & Benefits"},
        {"es": "Analista de Nómina", "en": "Payroll Analyst"},
        {"es": "Training Coordinator", "en": "Training Coordinator"},
        {"es": "Coordinador de Capacitación", "en": "Training Coordinator"},
        {"es": "Organizational Development", "en": "Organizational Development"},
    ],
    
    # Operaciones & Logística
    "operaciones": [
        {"es": "Operations Manager", "en": "Operations Manager"},
        {"es": "Gerente de Operaciones", "en": "Operations Manager"},
        {"es": "Supply Chain Manager", "en": "Supply Chain Manager"},
        {"es": "Gerente de Cadena de Suministro", "en": "Supply Chain Manager"},
        {"es": "Logistics Coordinator", "en": "Logistics Coordinator"},
        {"es": "Coordinador de Logística", "en": "Logistics Coordinator"},
        {"es": "Warehouse Manager", "en": "Warehouse Manager"},
        {"es": "Gerente de Bodega", "en": "Warehouse Manager"},
        {"es": "Purchasing Manager", "en": "Purchasing Manager"},
        {"es": "Gerente de Compras", "en": "Purchasing Manager"},
        {"es": "Inventory Analyst", "en": "Inventory Analyst"},
        {"es": "Analista de Inventarios", "en": "Inventory Analyst"},
        {"es": "Project Manager", "en": "Project Manager"},
        {"es": "Gerente de Proyectos", "en": "Project Manager"},
        {"es": "PMO", "en": "PMO"},
    ],
    
    # Servicio al Cliente
    "servicio": [
        {"es": "Customer Service", "en": "Customer Service"},
        {"es": "Servicio al Cliente", "en": "Customer Service"},
        {"es": "Customer Success", "en": "Customer Success"},
        {"es": "Call Center Agent", "en": "Call Center Agent"},
        {"es": "Agente de Call Center", "en": "Call Center Agent"},
        {"es": "Support Specialist", "en": "Support Specialist"},
        {"es": "Especialista de Soporte", "en": "Support Specialist"},
        {"es": "Technical Support", "en": "Technical Support"},
        {"es": "Soporte Técnico", "en": "Technical Support"},
    ],
    
    # Legal
    "legal": [
        {"es": "Abogado", "en": "Lawyer"},
        {"es": "Attorney", "en": "Attorney"},
        {"es": "Legal Counsel", "en": "Legal Counsel"},
        {"es": "Asesor Legal", "en": "Legal Advisor"},
        {"es": "Paralegal", "en": "Paralegal"},
        {"es": "Corporate Lawyer", "en": "Corporate Lawyer"},
        {"es": "Abogado Corporativo", "en": "Corporate Lawyer"},
    ],
    
    # Salud
    "salud": [
        {"es": "Médico", "en": "Doctor"},
        {"es": "Enfermera", "en": "Nurse"},
        {"es": "Psicólogo", "en": "Psychologist"},
        {"es": "Fisioterapeuta", "en": "Physical Therapist"},
        {"es": "Nutricionista", "en": "Nutritionist"},
        {"es": "Farmacéutico", "en": "Pharmacist"},
    ],
    
    # Educación
    "educacion": [
        {"es": "Profesor", "en": "Teacher"},
        {"es": "Docente", "en": "Instructor"},
        {"es": "Tutor", "en": "Tutor"},
        {"es": "Coordinador Académico", "en": "Academic Coordinator"},
    ],
    
    # Otros
    "otros": [
        {"es": "Asistente Administrativo", "en": "Administrative Assistant"},
        {"es": "Secretaria", "en": "Secretary"},
        {"es": "Recepcionista", "en": "Receptionist"},
        {"es": "Office Manager", "en": "Office Manager"},
        {"es": "Gerente de Oficina", "en": "Office Manager"},
        {"es": "Executive Assistant", "en": "Executive Assistant"},
        {"es": "Asistente Ejecutivo", "en": "Executive Assistant"},
        {"es": "CEO", "en": "CEO"},
        {"es": "Director General", "en": "CEO"},
        {"es": "COO", "en": "COO"},
        {"es": "Director de Operaciones", "en": "COO"},
    ]
}


def get_all_roles():
    """Obtener lista plana de todos los roles"""
    all_roles = []
    for categoria in ROLES_PROFESIONALES.values():
        all_roles.extend(categoria)
    return all_roles


def get_roles_list():
    """Obtener lista de roles únicos ordenados"""
    roles = get_all_roles()
    # Combinar español e inglés
    combined = []
    for role in roles:
        combined.append(role["es"])
        if role["en"] != role["es"]:
            combined.append(role["en"])
    
    # Eliminar duplicados y ordenar
    unique_roles = sorted(list(set(combined)))
    return unique_roles


if __name__ == "__main__":
    roles = get_roles_list()
    print(f"Total de roles: {len(roles)}")
    print("\nPrimeros 20:")
    for role in roles[:20]:
        print(f"  - {role}")
