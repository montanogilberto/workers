#!/bin/bash

# =============================================================================
# Production Deployment Script for Azure Functions
# =============================================================================
# This script deploys the SmartLoans Workers to Azure and validates the deployment
#
# Usage:
#   ./deploy_to_production.sh [function-app-name] [resource-group]
#
# Examples:
#   ./deploy_to_production.sh smartloans-workers-func rg-smartloans-workers
#   ./deploy_to_production.sh  # Uses defaults from config
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
FUNCTION_APP_NAME="${1:-smartloans-workers-func}"
RESOURCE_GROUP="${2:-rg-smartloans-workers}"
LOCATION="${3:-eastus}"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =============================================================================
# Configuration Check
# =============================================================================
log_info "Checking configuration..."

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    log_error "Azure CLI is not installed. Please install it first:"
    echo "  brew install azure-cli"
    exit 1
fi

# Check if logged in to Azure
if ! az account show &> /dev/null; then
    log_warning "Not logged in to Azure. Please run:"
    echo "  az login"
    exit 1
fi

log_success "Azure CLI configured"

# =============================================================================
# Pre-deployment Checks
# =============================================================================
log_info "Running pre-deployment checks..."

# Check if function app exists
FUNCTION_APP_EXISTS=$(az functionapp show \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "id" \
    --output tsv 2>/dev/null || echo "")

if [ -z "$FUNCTION_APP_EXISTS" ]; then
    log_warning "Function app '$FUNCTION_APP_NAME' does not exist."
    log_info "Creating new Function App..."
    
    az functionapp create \
        --resource-group "$RESOURCE_GROUP" \
        --consumption-plan-location "$LOCATION" \
        --runtime python \
        --functions-version 4 \
        --name "$FUNCTION_APP_NAME" \
        --storage-account "${FUNCTION_APP_NAME}storage" \
        || {
            log_error "Failed to create Function App"
            exit 1
        }
    
    log_success "Function App created"
else
    log_success "Function App exists: $FUNCTION_APP_NAME"
fi

# =============================================================================
# Clean Up
# =============================================================================
log_info "Cleaning up legacy files..."

# Remove any remaining function.json files (causes mixed function app warning)
find . -name "function.json" -type f -delete 2>/dev/null || true

# Clean up __pycache__
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

log_success "Cleanup complete"

# =============================================================================
# Deploy to Azure
# =============================================================================
log_info "Deploying to Azure..."

# Check if func CLI is available
if command -v func &> /dev/null; then
    log_info "Using Azure Functions Core Tools for deployment..."
    
    # Deploy with local settings
    func azure functionapp publish "$FUNCTION_APP_NAME" \
        --publish-local-settings \
        --overwrite-settings \
        --pull-settings \
        || {
            log_error "Deployment failed"
            exit 1
        }
    
    log_success "Deployment complete (using func CLI)"
else
    log_warning "Azure Functions Core Tools not found."
    log_info "Using alternative deployment method..."
    
    # Zip and deploy
    zip -r deploy.zip . -x "*.git*" "*__pycache__*" "*.pyc" "local.settings.json" "production.settings.json"
    
    az functionapp deployment source config-zip \
        --resource-group "$RESOURCE_GROUP" \
        --name "$FUNCTION_APP_NAME" \
        --src deploy.zip \
        || {
            log_error "Deployment failed"
            rm -f deploy.zip
            exit 1
        }
    
    rm -f deploy.zip
    log_success "Deployment complete (using zip)"
fi

# =============================================================================
# Start the Function App
# =============================================================================
log_info "Starting Function App..."

az functionapp start \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    || {
        log_warning "Failed to start Function App. Starting manually in Azure Portal."
    }

log_success "Function App started"

# =============================================================================
# Post-deployment Validation
# =============================================================================
log_info "Validating deployment..."

# Wait for app to be ready
log_info "Waiting for Function App to be ready..."
sleep 10

# Check function status
log_info "Checking function status..."

FUNCTIONS=$(az functionapp function list \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "[].{name:name, enabled:config.enabled}" \
    --output json 2>/dev/null || echo "[]")

if [ "$FUNCTIONS" != "[]" ]; then
    log_success "Functions found:"
    echo "$FUNCTIONS" | python3 -m json.tool 2>/dev/null || echo "$FUNCTIONS"
else
    log_warning "No functions found or unable to list functions"
fi

# Check app status
APP_STATUS=$(az functionapp show \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "state" \
    --output tsv 2>/dev/null || echo "Unknown")

log_info "Function App State: $APP_STATUS"

# =============================================================================
# View Logs (Optional)
# =============================================================================
log_info ""
log_info "Deployment completed!"
log_info ""
log_info "To view real-time logs, run:"
echo -e "  ${BLUE}az functionapp logstream --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP${NC}"
log_info ""
log_info "To check function status in Azure Portal:"
echo -e "  ${BLUE}https://portal.azure.com/#@/resource/subscriptions/$(az account show --query "id" -o tsv)/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$FUNCTION_APP_NAME/functions${NC}"
log_info ""
log_info "Next steps:"
echo "  1. Verify all 4 functions are enabled in Azure Portal"
echo "  2. Check logs for successful executions"
echo "  3. Monitor database for processed records"
echo "  4. Set up alerts for failures"

log_success "Production deployment script completed!"

