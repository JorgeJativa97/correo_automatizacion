import cx_Oracle
import pandas as pd
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import ssl

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Cargar variables de entorno
load_dotenv()

def obtener_configuracion():
    """Obtener configuración desde variables de entorno"""
    # Calcular fecha de ayer (día anterior)
    ayer = datetime.now() - timedelta(days=1)
    fecha_ayer = ayer.strftime('%d-%m-%Y')
    
    return {
        "db_user": os.getenv("DB_USER"),
        "db_password": os.getenv("DB_PASSWORD"),
        "db_dsn": os.getenv("DB_DSN"),
        "email_from": os.getenv("EMAIL_FROM"),
        "email_password": os.getenv("EMAIL_PASSWORD"),
        "email_to": os.getenv("EMAIL_TO"),
        "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        "smtp_port": os.getenv("SMTP_PORT", 587),
        "query": (
            "SELECT F_DESCCOMPONENTE(EMI04CODI) RUBRO, SUM(VALOR) TOTAL "
            "FROM V_COBROSORIGEN "
            f"WHERE FPAGO BETWEEN TO_DATE('{fecha_ayer}', 'DD-MM-YYYY') AND TO_DATE('{fecha_ayer}', 'DD-MM-YYYY') "
            "AND TIPO LIKE '%NORMAL%' "
            "AND EMI04CODI IN (2860,2882,6,8,10,13,16,68,134,135) "
            "GROUP BY F_DESCCOMPONENTE(EMI04CODI) "
            "ORDER BY F_DESCCOMPONENTE(EMI04CODI)"
        )
    }

def generar_reporte(config):
    """Generar reporte desde Oracle y guardar como Excel"""
    try:
        logger.info("Conectando a Oracle...")
        
        # Parsear DSN (formato: host:port/service_name)
        host, port_service = config['db_dsn'].split(':', 1)
        port, service_name = port_service.split('/', 1)
        
        dsn = cx_Oracle.makedsn(host, int(port), service_name=service_name)
        
        with cx_Oracle.connect(
            user=config['db_user'],
            password=config['db_password'],
            dsn=dsn
        ) as connection:
            logger.info("✅ Conexión exitosa a Oracle")
            
            # Ejecutar consulta
            logger.info(f"Ejecutando consulta para fecha: {config['query'].split('BETWEEN')[1].split('AND')[0].strip()}")
            logger.info(f"Consulta completa: {config['query'][:100]}...")
            
            df = pd.read_sql(config['query'], connection)
            
            # Generar archivo
            fecha_reporte = datetime.now().strftime("%Y%m%d")
            filename = f"reporte_{fecha_reporte}.xlsx"
            df.to_excel(filename, index=False)
            logger.info(f"📊 Reporte generado: {filename}")
            
            # Mostrar preview
            logger.info(f"Registros obtenidos: {len(df)}")
            if not df.empty:
                logger.info("Primeras filas:\n" + str(df.head(3)))
            
            return filename
            
    except Exception as e:
        logger.error(f"🚨 Error en base de datos: {str(e)}")
        raise

def enviar_correo(config, archivo):
    """Enviar reporte por correo"""
    try:
        logger.info("Preparando envío de correo...")
        
        # Crear mensaje
        msg = MIMEMultipart()
        fecha_ayer = (datetime.now() - timedelta(days=1)).strftime('%d/%m/%Y')
        msg['Subject'] = f"Reporte Diario - {fecha_ayer}"
        msg['From'] = config['email_from']
        msg['To'] = config['email_to']
        
        # Cuerpo del correo
        body = f"""Buen día,

Adjunto el reporte diario correspondiente a la fecha {fecha_ayer}.

Saludos,
Sistema de Reportes Automatizados"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Adjuntar archivo
        with open(archivo, "rb") as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(archivo))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(archivo)}"'
            msg.attach(part)
        
        # Crear conexión segura
        context = ssl.create_default_context()
        
        # Enviar correo con depuración extendida
        try:
            logger.info(f"Conectando a {config['smtp_server']}:{config['smtp_port']}")
            with smtplib.SMTP(config['smtp_server'], int(config['smtp_port'])) as server:
                server.set_debuglevel(1)  # Activar depuración SMTP
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                logger.info("Autenticando...")
                server.login(config['email_from'], config['email_password'])
                logger.info("Enviando correo...")
                server.sendmail(config['email_from'], config['email_to'].split(','), msg.as_string())
            
            logger.info("✅ Correo enviado correctamente")
            
        except Exception as e:
            logger.error(f"🚨 Error SMTP: {str(e)}")
            # Intento adicional sin TLS para diagnóstico
            try:
                logger.warning("Intentando sin TLS...")
                with smtplib.SMTP(config['smtp_server'], int(config['smtp_port'])) as server:
                    server.set_debuglevel(1)
                    server.login(config['email_from'], config['email_password'])
                    server.sendmail(config['email_from'], config['email_to'], msg.as_string())
                logger.warning("✅ Correo enviado SIN TLS")
            except Exception as e2:
                logger.error(f"🚨 Error sin TLS: {str(e2)}")
            raise
        
    except Exception as e:
        logger.error(f"🚨 Error al enviar correo: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        logger.info("🚀 Iniciando generación de reporte...")
        config = obtener_configuracion()
        
        # Validar configuración
        if not all([config['db_user'], config['db_password'], config['db_dsn']]):
            raise ValueError("❌ Faltan credenciales de Oracle en el archivo .env")
        
        # Generar reporte
        archivo_reporte = generar_reporte(config)
        
        # Enviar correo si hay configuración de correo
        if config['email_from'] and config['email_password'] and config['email_to']:
            logger.info("Credenciales de correo detectadas. Enviando reporte...")
            enviar_correo(config, archivo_reporte)
        else:
            logger.warning("⚠️ Configuración de correo incompleta. No se enviará el reporte.")
            if not config['email_from']:
                logger.warning("Falta EMAIL_FROM")
            if not config['email_password']:
                logger.warning("Falta EMAIL_PASSWORD")
            if not config['email_to']:
                logger.warning("Falta EMAIL_TO")
        
        logger.info("✅ Proceso completado exitosamente!")
    except Exception as e:
        logger.exception("❌ Error crítico en el proceso principal")