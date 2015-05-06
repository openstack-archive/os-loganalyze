# Copyright (c) 2015 Rackspace Australia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

# check for service enabled
if is_service_enabled os_loganalyze; then

    if [[ "$1" == "stack" && "$2" == "pre-install" ]]; then
        # Set up system services
        echo_summary "Configuring system services os_loganalyze"
        install_apache_wsgi
        if is_ubuntu; then
            # rewrite isn't enabled by default, enable it
            sudo a2enmod rewrite
        elif is_fedora; then
            # rewrite is enabled by default, noop
            echo "rewrite mod already enabled"
        elif is_suse; then
            # WSGI isn't enabled by default, enable it
            sudo a2enmod rewrite
        else
            exit_distro_not_supported "apache mod-rewrite installation"
        fi

    elif [[ "$1" == "stack" && "$2" == "install" ]]; then
        # Perform installation of service source
        echo_summary "Installing os_loganalyze"
        setup_install $OS_LOGANALYZE_DIR

    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        # Configure after the other layer 1 and 2 services have been configured
        echo_summary "Configuring os_loganalyze"

        sudo cp $OS_LOGANALYZE_APACHE_TEMPLATE $(apache_site_config_for os_loganalyze)
        sudo sed -e "
            s/%PORT%/8080/g;
            s/%OS_LOGANALYZE_DIR%/${OS_LOGANALYZE_DIR//\//\\\/}/g;
        " -i $(apache_site_config_for os_loganalyze)

        enable_apache_site os_loganalyze
        restart_apache_server

    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        # Initialize and start the os_loganalyze service
        echo_summary "Initializing os_loganalyze"
    fi

    if [[ "$1" == "unstack" ]]; then
        # Shut down os_loganalyze services
        # no-op
        stop_apache_server
    fi

    if [[ "$1" == "clean" ]]; then
        # Remove state and transient data
        # Remember clean.sh first calls unstack.sh
        # no-op
        disable_apache_site os_loganalyze
        if is_ubuntu; then
            # rewrite isn't enabled by default, disable it agin
            sudo a2dismod rewrite
        elif is_fedora; then
            # rewrite is enabled by default, noop
            echo "rewrite mod enabled by default"
        elif is_suse; then
            # rewrite isn't enabled by default, disable it agin
            sudo a2dismod rewrite
        else
            exit_distro_not_supported "apache mod-rewrite installation"
        fi
    fi
fi