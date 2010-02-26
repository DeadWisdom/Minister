Icon = Tea.Element.subclass({
    options: {
        cls: 'icon',
        type: '',
        status: 'active',
        colors: {
            "active":       "green",
            "struggling":   "green",
            "updating":     "gray",
            "deploying":    "gray",
            "redeploying":  "gray",
            "withdrawing":  "gray",
            "disabled":     "gray",
            "unknown":      "gray",
            "failed":       "red",
            "mia":          "red"
        }
    },
    setValue : function(status, type)
    {
        this._img = App.root + 'static/icons/' + type + '-' + this.options.colors[status] + '.png';
        if (this.source)
            this.source.css('background-image', "url(" + this._img + ")");
    },
    onRender : function()
    {
        if (this._img)
            this.source.css('background-image', this._img);
        else
            this.setValue(this.options.status, this.options.type);
    }
});

DeploymentItem = Tea.Container.subclass({
    options: {
        cls: 'deployment item',
        value: null
    },
    onInit : function()
    {
        this.icon = new Icon();
        this.name = new Tea.Element({cls: 'name'});
        this.url =  new Tea.Element({cls: 'url'});
        this.info = new Tea.Element({cls: 'info'});
        
        this.append(this.icon);
        this.append(this.name);
        this.append(this.url);
        this.append(this.info);
    },
    onRender : function()
    {
        this.setValue(this.options.value);
    },
    setValue : function(v)
    {
        this.source.attr('class', 'deployment item ' + v.status + ' ' + v.type);
        
        this.icon.setValue(v.status, v.type);
        this.name.setHTML(v.name);
        this.url.setHTML(v.url);
        if (v.statusText)
            this.info.setHTML(v.status + " &ndash; " + v.statusText);
        else
            this.info.setHTML(v.status);
    },
    setFail : function(v)
    {
        this.source.attr('class', 'deployment item unknown');
        this.info.setHTML('unkown');
    }
});

LoadingElement = Tea.Element.subclass({
    options: {
        cls: 'loading item',
        value: null
    },
    onRender : function()
    {
        $('<div class="loading-icon icon"/>').appendTo(this.source);
        
        $('<div class="name">')
          .append("Loading")
          .appendTo(this.source);
    }
})

var App = new Tea.Application({
    stack: new Tea.StackContainer({ 
        skin: Tea.StackContainer.StretchySkin,
        column_width: 300
    }),
    
    ready : function()
    {
        this.stack.render().appendTo('#main');
        
        this.deployments = {};
        this.deployment_panel = new Tea.Panel({title: 'Deployments'});
        this.stack.push( this.deployment_panel );
        
        this.deployment_panel.append( this.loading = new LoadingElement() );
        
        this.load();
    },
    
    load : function()
    {
        $.ajax({
            url: App.root + 'deployments.json', 
            success: Tea.method(this.onLoad, this),
            dataType: "json",
        });
    },
    
    onLoad : function(deployments, status_code, request)
    {
        if (deployments == null)
        {
            this.timer = setTimeout(Tea.method(this.load, this), 3000);
            return this.onFail();
        }
        
        this.deployment_panel.remove( this.loading );
        
        var all = {};
        for(var i=0; i<deployments.length; i++)
        {
            this.setDeployment(deployments[i]);
            all[deployments[i].path] = true;
        }
        
        for(var path in this.deployments)
        {
            if (!all[path])
            {
                this.deployments[path].remove();
                delete this.deployments[path];
            }
        }
        
        this.timer = setTimeout(Tea.method(this.load, this), 1000);
    },
    
    onFail : function()
    {
        for(var path in this.deployments)
        {
            this.deployments[path].setFail();
        }
    },
    
    setDeployment : function(value)
    {
        if (this.deployments[value.path])
        {
            this.deployments[value.path].setValue(value);
        }
        else
        {
            var d = this.deployments[value.path] = new DeploymentItem({
                value: value
            });
            this.deployment_panel.append(d);
        }
    }
})